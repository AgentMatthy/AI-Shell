#!/usr/bin/env python

import json
import subprocess
from pathlib import Path
from rich.console import Console
from openai import OpenAI

class ChatManager:
    def __init__(self, config, model_manager, conversation_manager=None, web_search_manager=None):
        self.config = config
        self.model_manager = model_manager
        self.conversation_manager = conversation_manager
        self.web_search_manager = web_search_manager
        self.console = Console()
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
            self.console.print(f"[yellow]Warning: Failed to initialize incognito client: {e}[/yellow]")
    
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
        """Load additional instructions from context file next to config.yaml"""
        try:
            # Always look for context.md next to config.yaml in project root
            project_root = Path(__file__).parent.parent  # Go up from src/ to project root
            context_path = project_root / "context.md"
            
            # Check if file exists and read it
            if context_path.exists() and context_path.is_file():
                with open(context_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                if content:
                    return f"\n\nADDITIONAL GUIDELINES AND INFORMATION FROM THE USER:\n{content}"
            
            return ""
            
        except Exception as e:
            # Silently handle errors - don't break the system if context file has issues
            self.console.print(f"[yellow]Warning: Could not load context file: {e}[/yellow]")
            return ""
    
    def _get_system_prompt(self):
        """Get the system prompt for the AI assistant"""
        web_search_info = ""
        if self.web_search_manager and self.web_search_manager.is_available():
            web_search_info = """

WEB SEARCH CAPABILITY:
You have access to web search functionality. When you need current information, documentation, or answers that are not available through local commands, use web search blocks like this:

```websearch
query terms here
```

Use web search when you need to:
- Find current information about software, libraries, or technologies
- Look up documentation, tutorials, or guides
- Get answers to questions that require current knowledge
- Find solutions to specific error messages or problems
- Research best practices or current recommendations

Example:
"Let me search for the latest installation instructions for Docker:

```websearch
Docker installation Ubuntu 2024 latest
```"

IMPORTANT: Like commands, use ONLY ONE web search block per response."""

# ------------------------- #
        
        additional_instructions = self._load_additional_instructions()
        
        return f"""
You are a Linux terminal assistant Agent. You can provide explanations and execute commands naturally.{web_search_info}

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
3. You can mix explanations and commands/searches naturally in the same response
4. Each command or search block should contain exactly one command or query
5. CRITICAL: Use ONLY ONE command OR search block per response - NEVER multiple
6. Always explain what the command or search will do
7. After each command/search, wait to see the result before proceeding
8. Execute commands/searches one at a time and analyze results before continuing
9. ALWAYS end your response with the appropriate tag: [QUESTION], [COMPLETE], or no tag

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
            self.console.print("\n[yellow]Response generation interrupted by user.[/yellow]")
            return None, None
        except Exception as e:
            # Remove the user message from payload since we're cancelling
            if self.payload and self.payload[-1]["role"] == "user":
                self.payload.pop()
            self.console.print(f"[red]Error generating chat response: {e}[/red]")
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
        try:
            # Get the current model name and client for the API request
            model_name = self.get_current_model_name()
            client = self.get_current_client()
            
            # Make streaming API request - shows "Processing..." during connection establishment
            with self.console.status("[bold cyan]Processing...[/bold cyan]", spinner_style="cyan"):
                response = client.chat.completions.create(
                    model=model_name, 
                    messages=self.payload, 
                    stream=True
                )
            
            # Process the streaming response - shows "Thinking..." during content generation
            
            reply_chunk = []
            reasoning_chunk = []
            full_reply = ""
            has_reasoning = False
            
            with self.console.status("[bold green]Thinking...[/bold green]") as status:
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
            self.console.print("\n[yellow]Response generation interrupted by user.[/yellow]")
            return None, None
        except ConnectionError as e:
            self.console.print(f"[red]Connection error: Unable to reach API server. {e}[/red]")
            return None, None
        except TimeoutError as e:
            self.console.print(f"[red]Request timeout: API server took too long to respond. {e}[/red]")
            return None, None
        except json.JSONDecodeError as e:
            self.console.print(f"[red]Invalid response format from API: {e}[/red]")
            return None, None
        except Exception as e:
            self.console.print(f"[red]Unexpected error in _generate_response: {e}[/red]")
            return None, None

    def clear_history(self):
        """Clear conversation history"""
        self.payload = [{"role": "system", "content": self._get_system_prompt()}]
        
        # Update conversation manager if available
        if self.conversation_manager:
            self.conversation_manager.clear_conversation()
        # self.console.print("[yellow]Conversation history cleared.[/yellow]")
