#!/usr/bin/env python

import json
import subprocess
from pathlib import Path
from openai import OpenAI

from .theme import create_console, get_theme

class ChatManager:
    def __init__(self, config, model_manager, conversation_manager=None, web_search_manager=None, context_manager=None):
        self.config = config
        self.model_manager = model_manager
        self.conversation_manager = conversation_manager
        self.web_search_manager = web_search_manager
        self.context_manager = context_manager
        self.theme = get_theme(config)
        self.console = create_console(config)
        self.payload = [{"role": "system", "content": self._get_system_prompt()}]
        self.incognito_mode = False
        
        # Initialize OpenAI client (normal mode)
        self.client = OpenAI(
            api_key=config["api"]["api_key"], 
            base_url=config["api"]["url"]
        )
        
        # Initialize incognito client if enabled
        self.incognito_client = None
        self._init_incognito_client()
    
    def _init_incognito_client(self):
        """Initialize the incognito mode client"""
        try:
            incognito_config = self.config.get("incognito", {})
            if incognito_config.get("enabled", True):
                api_config = incognito_config.get("api", {})
                self.incognito_client = OpenAI(
                    api_key=api_config.get("api_key", "ollama"),
                    base_url=api_config.get("url", "http://localhost:11434/v1")
                )
        except Exception as e:
            self.console.print(f"[warning]Warning: Failed to initialize incognito client: {e}[/warning]")
    
    def set_incognito_mode(self, incognito_mode: bool):
        """Set incognito mode state"""
        self.incognito_mode = incognito_mode
    
    def get_current_client(self):
        """Get the appropriate client based on current mode"""
        if self.incognito_mode and self.incognito_client:
            return self.incognito_client
        return self.client
    
    def get_current_model_name(self):
        """Get the current model name based on mode"""
        if self.incognito_mode:
            incognito_config = self.config.get("incognito", {})
            model_info = incognito_config.get("model", {})
            return model_info.get("name", "llama3.2:latest")
        else:
            return self.model_manager.get_current_model_for_api()
    
    def _load_additional_instructions(self):
        """Load additional instructions from context file in ~/.config/ai-shell/"""
        try:
            from .constants import CONTEXT_FILE_PATH
            
            # Check if file exists and read it
            if CONTEXT_FILE_PATH.exists() and CONTEXT_FILE_PATH.is_file():
                with open(CONTEXT_FILE_PATH, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                if content:
                    return f"\n\nADDITIONAL GUIDELINES AND INFORMATION FROM THE USER:\n{content}"
            
            return ""
            
        except Exception as e:
            # Silently handle errors - don't break the system if context file has issues
            self.console.print(f"[warning]Warning: Could not load context file: {e}[/warning]")
            return ""
    
    def _get_system_prompt(self):
        """Get the system prompt for the AI assistant"""
        web_search_info = ""
        if self.web_search_manager and self.web_search_manager.is_available():
            web_search_info = """

WEB SEARCH CAPABILITY:
You have access to a web search tool. This is NOT a traditional keyword-based search engine like Google — it is an AI-powered search model that understands natural language. You should ask it full, detailed questions rather than short keyword queries. Be as specific as needed — the search model will understand context and nuance.

Use web search blocks like this:

```websearch
your full question here
```

Use web search when you need to:
- Find current information about software, libraries, or technologies
- Look up documentation, tutorials, or guides
- Get answers to questions that require current knowledge
- Find solutions to specific error messages or problems
- Research best practices or current recommendations

Since the search tool is an AI model, write your queries as complete questions with full context. For example:

GOOD: "What is the recommended way to install Docker Engine on Ubuntu 24.04, and what are the prerequisites?"
BAD: "Docker installation Ubuntu 2024 latest"

GOOD: "How do I fix the Python error 'ModuleNotFoundError: No module named xyz' when using a virtual environment?"
BAD: "python modulenotfounderror xyz"

Example usage:
"Let me search for the recommended approach:

```websearch
What is the recommended way to install Docker Engine on Ubuntu 24.04, including repository setup and prerequisites?
```"

IMPORTANT: Like commands, use ONLY ONE web search block per response."""

# ------------------------- #

        context_management_info = """

CONTEXT MANAGEMENT:
You MUST actively manage your conversation context. After every command execution or search result, you should
immediately evaluate whether the output needs to be distilled or pruned BEFORE continuing with the next step.
Do NOT let outputs accumulate — manage them as soon as they have served their purpose.

CRITICAL RULE — TIMING:
- NEVER prune or distill information you are about to use in your VERY NEXT step.
- First USE the information (run the command, write the file, answer the question), THEN manage the context AFTERWARD.
- Example: if a web search tells you the package name is "helix", first run "sudo pacman -S helix", THEN distill the search result.
- Think: "Do I still need this for my next action?" If YES → do your action first, manage context later.

CRITICAL RULE — ALWAYS PREFER DISTILL OVER PRUNE:
- ALWAYS use context_distill instead of context_prune unless the message is completely irrelevant noise (e.g. a failed command you're retrying, a duplicate output, or a system confirmation message).
- Distilling preserves important information in a compact form. Pruning destroys it permanently.
- When distilling, include ALL important data in your summary: key results, file paths, version numbers, error messages, configuration values, package names — anything that could be useful later.
- Write thorough, information-dense summaries. A good distillation makes re-reading the original unnecessary.
- Only prune messages that contain ZERO useful information (e.g. "Context management applied" confirmations, completely superseded outputs, or empty/failed results you've already handled).

WHEN TO MANAGE (you must do this, it is not optional):
- AFTER you have already used the information and completed the step that needed it → DISTILL
- Package installation outputs, build logs, download progress → DISTILL to just the outcome (e.g. "neovim installed successfully")  
- File listings, config dumps you've already read and acted on → DISTILL to the key findings
- Outputs that are duplicated by newer outputs (e.g. you read a file, edited it, then read it again) → PRUNE the older one
- Task continuation messages, error handling messages → PRUNE once resolved
- Large outputs where you only needed a small piece of information → DISTILL to just that information
- When you see the <prunable-messages> list has entries, evaluate each one and manage any that are stale

WHEN NOT TO MANAGE:
- The output contains information you need for your NEXT step (e.g. search results you haven't acted on yet, file contents you're about to edit)
- You just received the output and haven't used it yet — USE IT FIRST, then manage
- The output contains information the user might ask about later in this same task

Available tools:

1. context_distill - Condense a message to a short summary. PREFERRED — use this for almost all context management. Include all important data in the summary.
```context_distill
id: <message_id>
summary: <thorough summary with all key data — e.g. "installed nginx 1.24.0 successfully" or "file contains 3 server blocks on ports 80, 443, 8080">
```

2. context_prune - Remove messages entirely. Use ONLY for messages that are completely irrelevant noise or fully superseded duplicates.
```context_prune
ids: <id1>, <id2>, ...
```

3. context_untruncate - Reveal full content of an auto-truncated message if you need details hidden in the middle.
```context_untruncate
id: <message_id>
```

Rules:
- The <prunable-messages> list below shows manageable messages with IDs and token sizes
- Messages marked [truncated] have hidden content — use context_untruncate if needed
- Messages marked [already distilled] are already condensed — prune them if no longer needed
- Context management uses the same one-block-per-response rule as commands and searches
- After managing context, you will automatically continue with your task
- IMPORTANT: Your DEFAULT behavior after a command completes should be to manage its output, then continue. Do not skip this step.
- REMEMBER: Always write a brief message explaining what you're doing when managing context — it will be shown to the user."""
        
        additional_instructions = self._load_additional_instructions()
        
        return f"""
You are a Linux terminal assistant Agent. You can provide explanations and execute commands naturally.{web_search_info}{context_management_info}

COMMAND FORMAT: When you need to run a command, use command blocks like this:

```command
ls -la /home
```

You can include explanations before and after command blocks naturally:

Example response:
"Let me check what's in your home directory:

```command
ls -la /home
```

This will show all files including hidden ones."

RESPONSE TYPE TAGS: You must include one of these tags at the END of your response to indicate its type:
- [QUESTION] - When your response asks a question that requires user input, choice, or clarification
- [COMPLETE] - When you have provided a complete summary and think the task is fully done
- No tag - When you want to continue with more actions or await command results

Examples:
- "Which directory would you like to search? [QUESTION]"
- "The installation is complete and all files are properly configured. [COMPLETE]"
- "Let me check the system status first:" (no tag - continuing with actions)

RULES:
1. Use ```command blocks ONLY for commands you want executed
2. Use ```websearch blocks ONLY for web searches when you need current information or precise instructions (like documentation)
3. Use ```context_distill, ```context_prune, or ```context_untruncate blocks for managing conversation context
4. You can mix explanations and commands/searches naturally in the same response
5. Each command or search block should contain exactly one command or query
6. CRITICAL: Use ONLY ONE command, search, OR context management block per response - NEVER multiple
7. Always explain what the command or search will do
8. After each command/search, wait to see the result before proceeding
9. Execute commands/searches one at a time and analyze results before continuing
10. ALWAYS end your response with the appropriate tag: [QUESTION], [COMPLETE], or no tag

COMMAND EXECUTION STRATEGY:
- Execute EXACTLY ONE command OR search per response
- Wait for the result before deciding on the next step
- Analyze command/search output before proceeding
- Never assume commands will succeed - always check results first

INFORMATION GATHERING:
- NEVER assume system details - discover them with commands
- When uncertain about system info that commands can reveal, USE COMMANDS:
  * OS: 'uname -a', 'cat /etc/os-release', 'lsb_release -a'
  * Software: 'which', 'command -v', 'dpkg -l', 'rpm -qa', 'pacman -Q'
  * Config: 'cat', 'grep', 'find' for config files
  * Hardware: 'lscpu', 'free -h', 'df -h', 'lsblk'
  * Network: 'ip addr', 'netstat', 'ss'
  * Processes: 'ps', 'top', 'systemctl'
- When you need current information not available locally, USE WEB SEARCH
- When multiple approaches exist and choice matters, ASK THE USER
- Examples: "Do you want to install via apt, snap, or compile from source?"

The host OS is Linux - use appropriate Linux commands only.{additional_instructions}
"""
    
    def get_chat_response(self, user_input):
        """Get response from the chat API with streaming"""
        try:
            # Add user message to payload
            self.payload.append({"role": "user", "content": user_input})
            
            # Generate response using the same method as get_response_without_user_input
            return self._generate_response()
                
        except KeyboardInterrupt:
            # Remove the user message from payload since we're cancelling
            if self.payload and self.payload[-1]["role"] == "user":
                self.payload.pop()
            self.console.print("\n[warning]Response generation interrupted by user.[/warning]")
            return None, None
        except Exception as e:
            # Remove the user message from payload since we're cancelling
            if self.payload and self.payload[-1]["role"] == "user":
                self.payload.pop()
            self.console.print(f"[error]Error generating chat response: {e}[/error]")
            return None, None
    

    
    
    
    def parse_response_type(self, response):
        """Parse response type from response tags"""
        if not response:
            return "continue"
        
        response_lower = response.lower().strip()
        
        if response_lower.endswith("[question]"):
            return "question"
        elif response_lower.endswith("[complete]"):
            return "complete"
        else:
            return "continue"
    
    def is_question(self, response):
        """Check if response contains a question tag"""
        return self.parse_response_type(response) == "question"
    
    def is_complete(self, response):
        """Check if response indicates task completion"""
        return self.parse_response_type(response) == "complete"
    
    def strip_response_tags_for_display(self, response):
        """Remove response tags from response for display purposes while keeping original in payload"""
        if not response:
            return response
        
        # Remove [QUESTION], [COMPLETE] tags from the end of the response
        response_stripped = response.rstrip()
        
        if response_stripped.lower().endswith("[question]"):
            return response_stripped[:-10].rstrip()
        elif response_stripped.lower().endswith("[complete]"):
            return response_stripped[:-10].rstrip()
        
        return response
    
    def send_system_notification(self, title, message):
        """Send a system notification using notify-send"""
        try:
            subprocess.run([
                "notify-send", 
                "--app-name=AI-Shell",
                "--icon=dialog-information",
                title, 
                message
            ], check=False, capture_output=True)
        except Exception:
            # Silently fail if notifications aren't available
            pass
    
    def get_response_without_user_input(self):
        """Get response from the chat API without adding any new user input"""
        # Generate response from current conversation payload without adding new user input
        return self._generate_response()
    
    def _generate_response(self):
        """Internal method to generate response from current payload"""
        t = self.theme
        try:
            # Get the current model name and client for the API request
            model_name = self.get_current_model_name()
            client = self.get_current_client()
            
            # Prepare clean messages for the API (strip metadata fields)
            if self.context_manager:
                api_messages = self.context_manager.prepare_messages_for_api(self.payload)
                # Inject prunable messages list into system prompt copy
                prunable_list = self.context_manager.get_prunable_list(self.payload)
                if prunable_list and api_messages and api_messages[0]["role"] == "system":
                    api_messages[0]["content"] += f"\n\n{prunable_list}"
            else:
                api_messages = self.payload
            
            # Make streaming API request - shows "Processing..." during connection establishment
            with self.console.status(f"[bold accent]Processing...[/bold accent]", spinner_style=t["accent"]):
                response = client.chat.completions.create(
                    model=model_name, 
                    messages=api_messages, 
                    stream=True
                )
            
            # Process the streaming response - shows "Thinking..." during content generation
            
            reply_chunk = []
            reasoning_chunk = []
            full_reply = ""
            has_reasoning = False
            
            with self.console.status(f"[bold accent_alt]Thinking...[/bold accent_alt]") as status:
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        reply_chunk.append(content)
                        full_reply += content
                    
                    if hasattr(chunk.choices[0].delta, 'reasoning_content'):
                        reasoning_content = getattr(chunk.choices[0].delta, 'reasoning_content', None)
                        if reasoning_content:
                            has_reasoning = True
                            reasoning_chunk.append(reasoning_content)
                            status.stop()
                            print(reasoning_content, end="")
                        
            if has_reasoning:
                print()
            
            assistant_response = "".join(reply_chunk)
            
            # Add assistant response to payload
            self.payload.append({"role": "assistant", "content": assistant_response})
            
            # Update conversation manager if available
            if self.conversation_manager:
                self.conversation_manager.update_payload(self.payload)
            
            return assistant_response, "".join(reasoning_chunk)
                
        except KeyboardInterrupt:
            self.console.print(f"\n[warning]Response generation interrupted by user.[/warning]")
            return None, None
        except ConnectionError as e:
            self.console.print(f"[error]Connection error: Unable to reach API server. {e}[/error]")
            return None, None
        except TimeoutError as e:
            self.console.print(f"[error]Request timeout: API server took too long to respond. {e}[/error]")
            return None, None
        except json.JSONDecodeError as e:
            self.console.print(f"[error]Invalid response format from API: {e}[/error]")
            return None, None
        except Exception as e:
            self.console.print(f"[error]Unexpected error in _generate_response: {e}[/error]")
            return None, None

    def clear_history(self):
        """Clear conversation history"""
        self.payload = [{"role": "system", "content": self._get_system_prompt()}]
        
        # Update conversation manager if available
        if self.conversation_manager:
            self.conversation_manager.clear_conversation()
