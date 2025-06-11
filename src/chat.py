#!/usr/bin/env python

import json
import requests
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
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=config["api"]["api_key"], 
            base_url=config["api"]["url"]
        )
    
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

RULES:
1. Use ```command blocks ONLY for commands you want executed
2. Use ```websearch blocks ONLY for web searches when you need current information
3. You can mix explanations and commands/searches naturally in the same response
4. Each command or search block should contain exactly one command or query
5. CRITICAL: Use ONLY ONE command OR search block per response - NEVER multiple
6. Always explain what the command or search will do
7. After each command/search, wait to see the result before proceeding
8. Execute commands/searches one at a time and analyze results before continuing

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

The host OS is Linux - use appropriate Linux commands only.
"""
    
    def get_chat_response(self, user_input):
        """Get response from the chat API with streaming"""
        try:
            # Add user message to payload
            self.payload.append({"role": "user", "content": user_input})
            
            # Get the current model for API
            model_name = self.model_manager.get_current_model_for_api()
            
            # Make streaming API request
            response = self.client.chat.completions.create(
                model=model_name, 
                messages=self.payload, 
                stream=True
            )
            
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
            
            return assistant_response, ""
                
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Response generation interrupted by user.[/yellow]")
            # Remove the user message from payload since we're cancelling
            if self.payload and self.payload[-1]["role"] == "user":
                self.payload.pop()
            return None, None
        except Exception as e:
            self.console.print(f"[red]Unexpected error: {e}[/red]")
            return None, None
    
    def check_task_status(self, command_output, original_request):
        """Check if a task was completed successfully using the task checker model"""
        try:
            prompt = f"""You are a task completion checker. Analyze the command output and determine if the user's original request was successfully completed.

Original request: {original_request}

Command output:
{command_output}

Respond with ONLY a JSON object in this exact format:
{{"completed": true/false, "reason": "brief explanation"}}

Do not include any other text or formatting."""

            # Use task checker model
            model_name = self.model_manager.get_task_checker_model_for_api()
            
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config['api']['api_key']}"
            }
            
            with self.console.status("[bold bright_black]Checking...[/bold bright_black]", spinner_style="bright_black"):
                response = requests.post(
                    f"{self.config['api']['url']}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
            
            if response.status_code == 200:
                data = response.json()
                result_text = data["choices"][0]["message"]["content"].strip()
                
                # Try to parse JSON response
                try:
                    result = json.loads(result_text)
                    return result.get("completed", False), result.get("reason", "No reason provided")
                except json.JSONDecodeError:
                    # Fallback: look for completion indicators in the response
                    result_lower = result_text.lower()
                    if any(indicator in result_lower for indicator in ["completed", "success", "done", "finished"]):
                        return True, result_text
                    else:
                        return False, result_text
            else:
                self.console.print(f"[yellow]Warning: Task status check failed (API Error {response.status_code})[/yellow]")
                return None, "Task status check unavailable"
                
        except Exception as e:
            self.console.print(f"[yellow]Warning: Task status check failed: {e}[/yellow]")
            return None, "Task status check unavailable"
    
    def check_if_question(self, ai_response):
        """Check if the AI's response is asking a question that requires user input"""
        try:
            prompt = f"""You are analyzing an AI assistant's response to determine if it contains a question that requires user input.

AI Response: {ai_response}

Determine if this response contains a question that requires the user to provide input, make a choice, or clarify something.

Examples of responses that ARE questions requiring user input:
- "Which directory would you like to search?"
- "Do you want to install via apt or snap?"
- "What filename should I use?"
- "Please specify the target directory"

Examples of responses that are NOT questions requiring user input:
- "Here's the information you requested"
- "The command completed successfully"
- "I found 3 files in the directory"
- "The installation is complete"

Respond with ONLY:
- "[QUESTION]" - if the response requires user input
- "[NO_QUESTION]" - if the response does not require user input

It is VERY important to only use one of these responses, as if you reply with anything else, it will break the parsing."""

            # Use task checker model for consistency
            model_name = self.model_manager.get_task_checker_model_for_api()
            
            with self.console.status("[bold bright_black]Analyzing...[/bold bright_black]", spinner_style="bright_black"):
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "system", "content": prompt}],
                    stream=False
                )
            
            content = response.choices[0].message.content
            if content:
                result = content.strip()
                return "[QUESTION]" in result
            return False
            
        except Exception as e:
            self.console.print(f"[yellow]Warning: Question check failed: {e}[/yellow]")
            # Default to assuming it's not a question to avoid breaking the flow
            return False
    
    def get_response_without_user_input(self):
        """Get response from the chat API without adding any new user input"""
        # Generate response from current conversation payload without adding new user input
        return self._generate_response()
    
    def _generate_response(self):
        """Internal method to generate response from current payload"""
        try:
            # Get the current model name for the API request
            model_name = self.model_manager.get_current_model_for_api()
            
            # Make streaming API request - shows "Processing..." during connection establishment
            with self.console.status("[bold cyan]Processing...[/bold cyan]", spinner_style="cyan"):
                response = self.client.chat.completions.create(
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
            # Add assistant response to payload
            self.payload.append({"role": "assistant", "content": assistant_response})
            
            # Update conversation manager if available
            if self.conversation_manager:
                self.conversation_manager.update_payload(self.payload)
            
            return assistant_response, "".join(reasoning_chunk)
                
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Response generation interrupted by user.[/yellow]")
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
