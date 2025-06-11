#!/usr/bin/env python

import re
import subprocess
from rich.markdown import Markdown
from rich.panel import Panel
from typing import Optional, List, Dict, Any

from .config import load_config
from .models import ModelManager
from .chat import ChatManager
from .ui import UIManager
from .commands import execute_command
from .conversation_manager import ConversationManager
from .terminal_input import TerminalInput


class AIShellApp:
    """Main application class for AI Shell Assistant"""
    
    def __init__(self):
        self.ui = UIManager()
        self.config: Optional[Dict[str, Any]] = None
        self.model_manager: Optional[ModelManager] = None
        self.conversation_manager: Optional[ConversationManager] = None
        self.chat_manager: Optional[ChatManager] = None
        self.terminal_input: Optional[TerminalInput] = None
        
        # Application state
        self.ai_mode = True
        self.max_retries = 10
        self.retry_count = 0
        self.original_request = ""
        self.conversation_history: List[str] = []
        self.rejudge = False
        self.rejudge_count = 0
    
    def initialize(self):
        """Initialize all components"""
        try:
            # Load configuration
            self.config = load_config()
            if self.config is None:
                raise RuntimeError("Failed to load configuration")
            
            # Initialize managers
            self.model_manager = ModelManager(self.config)
            self.conversation_manager = ConversationManager(self.config)
            self.chat_manager = ChatManager(self.config, self.model_manager, self.conversation_manager)
            self.terminal_input = TerminalInput(self.config)
            
            # Load settings
            settings = self.config.get("settings", {})
            self.max_retries = settings.get("max_retries", 10)
            self.ai_mode = settings.get("default_mode", "ai").lower() == "ai"
            
            # Check for conversation resume
            resume_session = self.conversation_manager.check_for_resume()
            if resume_session:
                resumed_payload = self.conversation_manager.resume_session(resume_session)
                self.chat_manager.payload = resumed_payload
            
            # Show welcome message if enabled
            if settings.get("show_welcome_message", True):
                self.ui.show_welcome()
                
        except Exception as e:
            self.ui.show_error(f"Failed to initialize application: {e}")
            raise
    
    def run(self):
        """Main application loop"""
        # Ensure all components are initialized
        assert self.chat_manager is not None, "Application not properly initialized"
        assert self.conversation_manager is not None, "Application not properly initialized"
        assert self.model_manager is not None, "Application not properly initialized"
        
        while True:
            try:
                if not self.rejudge:
                    self._reset_conversation_state()
                    user_input = self._get_user_input()
                    
                    # Handle input and check for exit/continue commands
                    action = self._handle_input(user_input)
                    
                    if action == "exit":
                        break
                    elif action == "continue":
                        continue
                    elif action == "switch_ai":
                        self.ai_mode = True
                        continue
                    elif action == "switch_direct":
                        self.ai_mode = False
                        continue
                    elif action == "direct_command":
                        continue
                    elif action == "process_ai":
                        self.original_request = user_input
                        # Add user input to payload
                        self.chat_manager.payload.append({"role": "user", "content": user_input})
                        self.conversation_manager.update_payload(self.chat_manager.payload, self.original_request)
                
                # Process AI response
                self._process_ai_response()
                
            except KeyboardInterrupt:
                self.ui.console.print("")
                continue
            except EOFError:
                self.ui.console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as error:
                self.ui.console.print(f"[red]Error occurred:[/red] {str(error)}")
                continue
    
    def _reset_conversation_state(self):
        """Reset conversation state for new interactions"""
        self.rejudge = False
        self.retry_count = 0
    
    def _get_user_input(self):
        """Get user input with enhanced terminal features"""
        assert self.terminal_input is not None
        assert self.model_manager is not None
        
        model_name = self.model_manager.get_model_display_name(self.model_manager.current_model)
        return self.terminal_input.get_input(self.ai_mode, model_name)
    
    def _handle_input(self, user_input: str) -> str:
        """Handle user input and return action to take"""
        if not user_input:
            return "continue"
        
        assert self.conversation_manager is not None
        assert self.chat_manager is not None
        assert self.model_manager is not None
        
        # Handle exit commands
        if user_input.lower() in ["/exit", "exit", "quit", ";q", ":q", "/q"]:
            self.conversation_manager.save_and_exit()
            return "exit"
        
        # Handle clear command
        if user_input.lower() in ["/clear", "/new", "/reset", "/c", "clear"]:
            subprocess.run("clear", shell=True)
            self.chat_manager.clear_history()
            return "continue"
        
        # Handle payload display command
        if user_input.lower() in ["/p", "/payload"]:
            self._show_payload()
            return "continue"
        
        # Handle help command
        if user_input.lower() in ["/help", "/h", "help"]:
            self.ui.show_help()
            return "continue"
        
        # Handle conversation management commands
        if self._handle_conversation_commands(user_input):
            return "continue"
        
        # Handle model commands
        if self._handle_model_commands(user_input):
            return "continue"
        
        # Handle mode switching commands
        if user_input.lower() == "/ai":
            return "switch_ai"
        elif user_input.lower() == "/dr":
            return "switch_direct"
        
        # Handle direct mode commands
        if not self.ai_mode:
            success, result = execute_command(user_input)
            if not success and result.strip():
                self.ui.console.print(f"[red]Command failed[/red]")
            return "direct_command"
        
        # AI mode - process with AI
        return "process_ai"
    
    def _show_payload(self):
        """Display current conversation payload"""
        assert self.chat_manager is not None
        assert self.config is not None
        
        self.ui.console.print("\n[bold cyan]Current Conversation Payload:[/bold cyan]")
        for i, message in enumerate(self.chat_manager.payload):
            role_color = {
                "system": "yellow",
                "user": "green", 
                "assistant": "blue"
            }.get(message["role"], "white")
            
            self.ui.console.print(f"\n[bold {role_color}][{i+1}] {message['role'].upper()}:[/bold {role_color}]")
            content = message["content"]
            settings = self.config.get("settings", {})
            truncate_length = settings.get("payload_truncate_length", 500)
            if len(content) > truncate_length:
                content = content[:truncate_length] + "... [truncated]"
            self.ui.console.print(Panel(content, border_style=role_color))
        
        self.ui.console.print(f"\n[dim]Total messages: {len(self.chat_manager.payload)}[/dim]")
    
    def _handle_conversation_commands(self, user_input: str) -> bool:
        """Handle conversation management commands"""
        assert self.conversation_manager is not None
        assert self.chat_manager is not None
        
        if user_input.lower() == "/save":
            self.conversation_manager.save_conversation()
            return True
        elif user_input.lower().startswith("/save "):
            name = user_input[6:].strip()
            self.conversation_manager.save_conversation(name)
            return True
        elif user_input.lower() == "/load":
            new_payload = self.conversation_manager.load_conversation()
            if new_payload is not None:
                self.chat_manager.payload = new_payload
            return True
        elif user_input.lower().startswith("/load "):
            name = user_input[6:].strip()
            new_payload = self.conversation_manager.load_conversation(name)
            if new_payload is not None:
                self.chat_manager.payload = new_payload
            return True
        elif user_input.lower() in ["/conversations", "/cv"]:
            self.conversation_manager.list_conversations()
            return True
        elif user_input.lower() == "/archive":
            if self.conversation_manager.archive_conversation():
                self.chat_manager.clear_history()
            return True
        elif user_input.lower().startswith("/delete "):
            name = user_input[8:].strip()
            self.conversation_manager.delete_conversation(name)
            return True
        elif user_input.lower() == "/status":
            self._show_status()
            return True
        
        return False
    
    def _handle_model_commands(self, user_input: str) -> bool:
        """Handle model management commands"""
        assert self.model_manager is not None
        
        if user_input.lower() in ["/models", "/model", "/m"]:
            self.model_manager.list_models()
            return True
        elif user_input.lower().startswith("/model "):
            model_alias = user_input[7:].strip()
            self.model_manager.switch_model(model_alias)
            return True
        
        return False
    
    def _show_status(self):
        """Show conversation status"""
        assert self.conversation_manager is not None
        
        status = self.conversation_manager.get_status_info()
        self.ui.console.print(f"\n[bold cyan]Conversation Status:[/bold cyan]")
        self.ui.console.print(f"Session ID: {status['session_id']}")
        self.ui.console.print(f"Started: {status['started_at']}")
        self.ui.console.print(f"Messages: {status['message_count']}")
        self.ui.console.print(f"Interactions: {status['interactions']}")
        self.ui.console.print(f"Status: {status['status']}")
        if status['original_request']:
            self.ui.console.print(f"Original request: {status['original_request']}")
    
    def _process_ai_response(self):
        """Process AI response and handle commands"""
        assert self.chat_manager is not None
        
        # Generate AI response
        response, _ = self.chat_manager.get_response_without_user_input()
        
        if not response:
            self.rejudge = False
            self.rejudge_count = 0
            self.retry_count = 0
            return
        
        # Handle empty response
        if not response.strip():
            self._handle_empty_response()
            return
        
        # Parse commands from response
        command_pattern = re.compile(r"```command\s*(.*?)\s*```", re.DOTALL)
        commands = command_pattern.findall(response)
        
        if commands:
            self._handle_command_response(response, commands)
        else:
            self._handle_text_response(response)
    
    def _handle_empty_response(self):
        """Handle empty AI response"""
        assert self.chat_manager is not None
        
        self.ui.console.print("[yellow]AI provided empty response - treating as task completion signal.[/yellow]")
        
        if self.original_request:
            self.chat_manager.payload.append({
                "role": "user", 
                "content": f"SYSTEM MESSAGE: Task appears to be complete for: {self.original_request}. Please provide a brief summary of what was accomplished."
            })
            self.rejudge = True
            self.original_request = ""
        else:
            self.chat_manager.payload.append({
                "role": "user", 
                "content": "SYSTEM MESSAGE: You provided an empty response. Please provide a proper response or explain why you cannot proceed."
            })
            self.rejudge = True
    
    def _handle_command_response(self, response, commands):
        """Handle response containing commands"""
        assert self.chat_manager is not None
        
        # Check for multiple commands
        if len(commands) > 1:
            self.ui.console.print(f"[red]Multiple commands detected ({len(commands)} commands). Asking AI to correct.[/red]")
            self.chat_manager.payload.append({
                "role": "user", 
                "content": f"SYSTEM MESSAGE: You provided {len(commands)} commands in one response, which is forbidden. You must provide EXACTLY ONE command per response. Please choose the FIRST command you need to execute and provide it alone with explanation."
            })
            self.rejudge = True
            self.rejudge_count += 1
            if self.rejudge_count > 3:
                self.ui.console.print(f"[red]Too many multiple command violations. Resetting conversation.[/red]")
                self.chat_manager.clear_history()
                self.rejudge = False
                self.rejudge_count = 0
            return
        
        # Process single command
        self.rejudge = False
        self.rejudge_count = 0
        
        # Display response
        md = Markdown(response)
        self.ui.console.print()
        self.ui.console.print(Panel(md, title="Response", border_style="blue"))
        self.ui.console.print()
        
        # Execute command
        command = commands[0].strip()
        if not command:
            self.ui.console.print("[yellow]Empty command block detected.[/yellow]")
            return
        
        self._execute_command_with_confirmation(command)
    
    def _handle_text_response(self, response):
        """Handle text-only response"""
        assert self.chat_manager is not None
        
        self.rejudge = False
        self.rejudge_count = 0
        
        # Display response
        md = Markdown(response)
        self.ui.console.print()
        self.ui.console.print(Panel(md, title="Summary", border_style="blue"))
        self.ui.console.print()
        
        # Check if task completion is needed
        if self.original_request:
            self.conversation_history.append(f"AI Reply: {response}")
            
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
            
            # Check if this is a question requiring user input
            is_question = self.chat_manager.check_if_question(response)
            
            if not is_question:
                # Check if task is complete
                conversation_context = "\n".join(self.conversation_history)
                completed, reason = self.chat_manager.check_task_status(conversation_context, self.original_request)
                
                if completed is False:
                    continue_context = f"SYSTEM MESSAGE: The original request ({self.original_request}) is not yet complete. Please continue with the next step."
                    self.chat_manager.payload.append({"role": "user", "content": continue_context})
                    self.rejudge = True
    
    def _execute_command_with_confirmation(self, command):
        """Execute command after user confirmation"""
        assert self.chat_manager is not None
        
        # Ask for confirmation
        panel_content = f"[bold white]Execute command:[/bold white] [cyan]`{command}`[/cyan]"
        self.ui.console.print(Panel(panel_content, title="[yellow]Command[/yellow]", border_style="yellow"))
        
        assert self.terminal_input is not None
        user_choice = self.terminal_input.get_confirmation("Proceed? [y/n]", "y").lower()
        
        if user_choice.lower() == "n":
            reason = self.terminal_input.get_reason_input("Reason for decline")
            feedback_context = f"SYSTEM MESSAGE: User declined to run the command: {command}\nReason: {reason}\n\nPlease provide an alternative approach to complete the original request: {self.original_request}"
            self.chat_manager.payload.append({"role": "user", "content": feedback_context})
            self.rejudge = True
        else:
            self._execute_and_process_command(command)
    
    def _execute_and_process_command(self, command):
        """Execute command and process results"""
        assert self.chat_manager is not None
        
        # Execute the command
        success, result = execute_command(command)
        
        if not success and result.strip():
            self.ui.console.print()
            self.ui.console.print(Panel(result, title=f"Error: {command}", border_style="red"))
            self.ui.console.print()
        
        # Track conversation
        self.conversation_history.append(f"Command: {command}")
        self.conversation_history.append(f"Output: {result}")
        self.conversation_history.append(f"Success: {success}")
        
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
        
        # Check task completion
        completed, reason = self.chat_manager.check_task_status(result, self.original_request)
        
        if completed is False:
            # Task needs more steps
            continue_context = f"SYSTEM MESSAGE: Command executed: {command}\nOutput: {result}\nSuccess: {success}\n\nThe original request is not yet complete. Please continue with the next step."
            self.chat_manager.payload.append({"role": "user", "content": continue_context})
            self.rejudge = True
        elif completed is None:
            # Task failed
            self._handle_task_failure(command, result, success)
        else:
            # Task is complete
            with self.ui.console.status("[bold green]Preparing summary...[/bold green]", spinner_style="green"):
                self.chat_manager.payload.append({"role": "user", "content": f"SYSTEM MESSAGE: Task completed. Please provide a brief summary of what was accomplished, or answer if the original request was a question."})
            self.rejudge = True
            self.retry_count = 0
            self.original_request = ""
    
    def _handle_task_failure(self, command, result, success):
        """Handle task failure with retry logic"""
        assert self.chat_manager is not None
        
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            with self.ui.console.status("[bold yellow]Preparing retry...[/bold yellow]", spinner_style="yellow"):
                failure_context = f"SYSTEM MESSAGE: Command executed but task status check failed.\nCommand: {command}\nOutput: {result}\nSuccess: {success}\n\nPlease try a different approach to complete: {self.original_request}"
                self.chat_manager.payload.append({"role": "user", "content": failure_context})
            self.rejudge = True
        else:
            self.ui.console.print(f"[yellow]Maximum retry attempts ({self.max_retries}) reached.[/yellow]")
            assert self.terminal_input is not None
            retry_choice = self.terminal_input.get_confirmation("Do you want to continue trying? [Y/n]", "N").upper()
            if retry_choice == "Y":
                self.retry_count = 0
                with self.ui.console.status("[bold yellow]Preparing retry...[/bold yellow]", spinner_style="yellow"):
                    failure_context = f"SYSTEM MESSAGE: Command executed but failed.\nCommand: {command}\nOutput: {result}\nSuccess: {success}\n\nUser requested to continue trying. Please try a different approach to complete: {self.original_request}"
                    self.chat_manager.payload.append({"role": "user", "content": failure_context})
                self.rejudge = True
            else:
                with self.ui.console.status("[bold red]Preparing summary...[/bold red]", spinner_style="red"):
                    self.chat_manager.payload.append({"role": "user", "content": f"SYSTEM MESSAGE: Task failed after {self.max_retries} attempts and user chose to stop. Please provide a summary of what was attempted and suggest alternatives."})
                self.rejudge = True
                self.retry_count = 0
