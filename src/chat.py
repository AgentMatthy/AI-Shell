#!/usr/bin/env python

# This is a Python script that uses the OpenAI API to interact with a Linux terminal.
# It is designed to be an agentic ai assistant that can execute commands and provide
# explanations based on the user's input.

import json
import requests
from rich.console import Console
from openai import OpenAI

class ChatManager:
    def __init__(self, config, model_manager):
        self.config = config
        self.model_manager = model_manager
        self.console = Console()
        self.payload = [{"role": "system", "content": self._get_system_prompt()}]
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=config["api"]["api_key"], 
            base_url=config["api"]["url"]
        )
    
    def _get_system_prompt(self):
        """Get the system prompt for the AI assistant"""
        return """
You are a Linux terminal assistant Agent. You can provide explanations and execute commands naturally.

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
2. You can mix explanations and commands naturally in the same response
3. Each command block should contain exactly one command
4. CRITICAL: Use ONLY ONE command block per response - NEVER multiple commands
5. Always explain what the command will do
6. After each command, wait to see the result before proceeding with additional commands
7. Execute commands one at a time and analyze results before continuing

COMMAND EXECUTION STRATEGY:
- Execute EXACTLY ONE command per response
- Wait for the result before deciding on the next step
- Analyze command output before proceeding
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
- When multiple approaches exist and choice matters, ASK THE USER
- Examples: "Do you want to install via apt, snap, or compile from source?"

The host OS is Linux - use appropriate Linux commands only.
"""
    
    def get_chat_response(self, user_input, system_prompt=None):
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
            
            return assistant_response, "".join(reasoning_chunk)
                
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
    
    def check_if_question(self, user_input):
        """Check if user input is a question or a task request"""
        question_indicators = ['?', 'what', 'how', 'why', 'when', 'where', 'who', 'which', 'can you tell', 'explain', 'describe']
        user_lower = user_input.lower().strip()
        
        # Check for question marks or question words
        if '?' in user_input:
            return True
        
        for indicator in question_indicators:
            if user_lower.startswith(indicator):
                return True
        
        return False
    
    def get_response_without_user_input(self):
        """Get response from the chat API without adding any new user input"""
        try:
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
            
            return assistant_response, "".join(reasoning_chunk)
                
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Response generation interrupted by user.[/yellow]")
            return None, None
        except Exception as e:
            self.console.print(f"[red]Unexpected error: {e}[/red]")
            return None, None

    def clear_history(self):
        """Clear conversation history"""
        self.payload = [{"role": "system", "content": self._get_system_prompt()}]
        # self.console.print("[yellow]Conversation history cleared.[/yellow]")
