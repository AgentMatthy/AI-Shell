#!/usr/bin/env python

import re
from rich.markdown import Markdown
from rich.panel import Panel
from typing import Optional, List, Dict, Any

from .config import load_config, reset_config
from .models import ModelManager
from .chat import ChatManager
from .ui import UIManager
from .commands import execute_command
from .command_safety import is_safe_command
from .constants import DEFAULT_SAFE_COMMANDS
from .conversation_manager import ConversationManager
from .terminal_input import TerminalInput
from .web_search import WebSearchManager
from .context_manager import ContextManager


class AIShellApp:
    """Main application class for AI Shell Assistant"""
    
    def __init__(self):
        self.ui = UIManager()
        self.config: Optional[Dict[str, Any]] = None
        self.model_manager: Optional[ModelManager] = None
        self.conversation_manager: Optional[ConversationManager] = None
        self.chat_manager: Optional[ChatManager] = None
        self.terminal_input: Optional[TerminalInput] = None
        self.web_search_manager: Optional[WebSearchManager] = None
        self.context_manager: Optional[ContextManager] = None
        
        
        # Application state
        self.ai_mode = True
        self.incognito_mode = False
        self.max_retries = 10
        self.retry_count = 0
        self.original_request = ""
        self.conversation_history: List[str] = []
        self.rejudge = False
        self.rejudge_count = 0
        self.auto_approve_commands = False
        self.safe_commands: set = set(DEFAULT_SAFE_COMMANDS)
    
    def initialize(self):
        """Initialize all components"""
        try:
            # Load configuration
            self.config = load_config()
            if self.config is None:
                raise RuntimeError("Failed to load configuration")
            
            # Initialize managers
            self.model_manager = ModelManager(self.config)
            self.conversation_manager = ConversationManager(self.config, self.ui)
            self.web_search_manager = WebSearchManager(self.config)
            self.context_manager = ContextManager(self.config)
            self.chat_manager = ChatManager(self.config, self.model_manager, self.conversation_manager, self.web_search_manager, self.context_manager)
            self.terminal_input = TerminalInput(self.config)
            
            # Load settings
            settings = self.config.get("settings", {})
            self.max_retries = settings.get("max_retries", 10)
            self.ai_mode = settings.get("default_mode", "ai").lower() == "ai"
            
            # Load safe commands for auto-approval
            if "safe_commands" in settings:
                custom_list = settings["safe_commands"]
                if isinstance(custom_list, list):
                    self.safe_commands = set(custom_list)
                else:
                    self.safe_commands = set(DEFAULT_SAFE_COMMANDS)
            else:
                self.safe_commands = set(DEFAULT_SAFE_COMMANDS)
            
            # Check for conversation resume
            resume_session = self.conversation_manager.check_for_resume()
            if resume_session:
                resumed_payload = self.conversation_manager.resume_session(resume_session)
                self.chat_manager.payload = resumed_payload
                self.context_manager.restore_ids_from_saved(resumed_payload)
            
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
                        # Reset auto-approve state for new requests
                        self.auto_approve_commands = False
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
        
        if self.incognito_mode:
            # Get incognito model display name
            incognito_config = self.config.get("incognito", {})
            model_info = incognito_config.get("model", {})
            model_name = model_info.get("display_name", "Local Model")
        else:
            model_name = self.model_manager.get_model_display_name(self.model_manager.current_model)
        
        return self.terminal_input.get_input(self.ai_mode, model_name, self.incognito_mode)
    
    def _handle_input(self, user_input: str) -> str:
        """Handle user input and return action to take"""
        if not user_input:
            return "continue"
        
        # Handle exit commands
        if user_input.lower() in ["/exit", "exit", "quit", ";q", ":q", "/q"]:
            self.conversation_manager.save_and_exit()
            return "exit"
        
        # Handle clear command
        if user_input.lower() in ["/clear", "/new", "/reset", "/c", "clear"]:
            import subprocess
            subprocess.run("clear", shell=True)
            self.chat_manager.clear_history()
            self.context_manager.reset()
            return "continue"
        
        # Handle payload display command
        if user_input.lower() in ["/p", "/payload"]:
            self._show_payload()
            return "continue"
        
        # Handle help command
        if user_input.lower() in ["/help", "/h", "help"]:
            self.ui.show_help()
            return "continue"
        
        # Handle '!' prefix for direct command execution
        if user_input.startswith("!"):
            command = user_input[1:].strip()
            if command:
                success, result = execute_command(command)
                if not success and result.strip():
                    self.ui.console.print(f"[red]Command failed[/red]")
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
        elif user_input.lower() == "/inc":
            self._toggle_incognito_mode()
            return "continue"
        elif user_input.lower() == "/compact":
            self._compact_payload()
            return "continue"
        elif user_input.lower() == "/resetconfig":
            self._handle_reset_config()
            return "continue"
        
        # Handle direct mode commands
        if not self.ai_mode:
            success, result = execute_command(user_input)
            if not success and result.strip():
                self.ui.console.print(f"[red]✗ Command failed[/red]")
            return "direct_command"
        
        # AI mode - process with AI
        return "process_ai"
    
    def _show_payload(self):
        """Display current conversation payload"""
        self.ui.console.print("\n[bold cyan]Current Conversation Payload:[/bold cyan]")
        for i, message in enumerate(self.chat_manager.payload):
            role_color = {
                "system": "yellow",
                "user": "green", 
                "assistant": "blue"
            }.get(message["role"], "white")
            
            # Show message ID and state if available
            msg_id = message.get("_msg_id")
            state = message.get("_state", "")
            id_str = f" (ctx #{msg_id})" if msg_id else ""
            state_str = f" [{state}]" if state and state != "normal" else ""
            
            self.ui.console.print(f"\n[bold {role_color}][{i+1}]{id_str}{state_str} {message['role'].upper()}:[/bold {role_color}]")
            content = message["content"]
            settings = self.config.get("settings", {})
            truncate_length = settings.get("payload_truncate_length", 500)
            if len(content) > truncate_length:
                content = content[:truncate_length] + "... [truncated]"
            from rich.panel import Panel
            self.ui.console.print(Panel(content, border_style=role_color))
        
        # Show context stats
        if self.context_manager:
            total_tokens = self.context_manager.get_total_tokens(self.chat_manager.payload)
            self.ui.console.print(f"\n[dim]Total messages: {len(self.chat_manager.payload)} | Estimated tokens: ~{total_tokens}[/dim]")
        else:
            self.ui.console.print(f"\n[dim]Total messages: {len(self.chat_manager.payload)}[/dim]")
    
    def _handle_conversation_commands(self, user_input):
        """Handle conversation management commands"""
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
                self.context_manager.restore_ids_from_saved(new_payload)
            return True
        elif user_input.lower().startswith("/load "):
            try:
                index_str = user_input[6:].strip()
                if index_str.isdigit():
                    index = int(index_str)
                    new_payload = self.conversation_manager.load_recent_conversation(index)
                    if new_payload is not None:
                        self.chat_manager.payload = new_payload
                        self.context_manager.restore_ids_from_saved(new_payload)
                else:
                    # Try loading by name if it's not a number
                    name = index_str
                    new_payload = self.conversation_manager.load_conversation(name)
                    if new_payload is not None:
                        self.chat_manager.payload = new_payload
                        self.context_manager.restore_ids_from_saved(new_payload)
            except ValueError:
                self.ui.console.print("[red]Invalid number format[/red]")
            return True
        elif user_input.lower().startswith(("/conversations", "/conversation", "/cv")):
            # Check for -r flag for removal
            parts = user_input.split()
            if len(parts) >= 2 and parts[1] == "-r":
                # Handle removal - get conversation name if provided
                name = parts[2] if len(parts) > 2 else None
                self.conversation_manager.delete_conversation(name)
            else:
                # Default behavior - list conversations
                self.conversation_manager.list_recent_conversations()
                self.ui.console.print()  # Add some spacing
                self.conversation_manager.list_conversations()
            return True
        elif user_input.lower() in ["/recent", "/r"]:
            self.conversation_manager.list_recent_conversations()
            return True
        elif user_input.lower() == "/archive":
            if self.conversation_manager.archive_conversation():
                self.chat_manager.clear_history()
                self.context_manager.reset()
            return True
        elif user_input.lower().startswith("/delete "):
            name = user_input[8:].strip()
            self.conversation_manager.delete_conversation(name)
            return True
        elif user_input.lower() == "/status":
            self._show_status()
            return True
        
        return False
    
    def _handle_model_commands(self, user_input):
        """Handle model management commands"""
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
        status = self.conversation_manager.get_status_info()
        self.ui.console.print(f"\n[bold cyan]Conversation Status:[/bold cyan]")
        self.ui.console.print(f"Session ID: {status['session_id']}")
        self.ui.console.print(f"Started: {status['started_at']}")
        self.ui.console.print(f"Messages: {status['message_count']}")
        self.ui.console.print(f"Interactions: {status['interactions']}")
        self.ui.console.print(f"Status: {status['status']}")
        if status['original_request']:
            self.ui.console.print(f"Original request: {status['original_request']}")
        
        # Show context stats
        if self.context_manager and self.chat_manager:
            total_tokens = self.context_manager.get_total_tokens(self.chat_manager.payload)
            prunable_count = sum(1 for msg in self.chat_manager.payload if msg.get("_prunable") and msg.get("_state") != "pruned")
            pruned_count = sum(1 for msg in self.chat_manager.payload if msg.get("_state") == "pruned")
            distilled_count = sum(1 for msg in self.chat_manager.payload if msg.get("_state") == "distilled")
            self.ui.console.print(f"\n[bold cyan]Context Stats:[/bold cyan]")
            self.ui.console.print(f"Estimated tokens: ~{total_tokens}")
            self.ui.console.print(f"Prunable messages: {prunable_count}")
            self.ui.console.print(f"Pruned: {pruned_count} | Distilled: {distilled_count}")
    
    def _toggle_incognito_mode(self):
        """Toggle incognito mode on/off"""
        self.incognito_mode = not self.incognito_mode
        
        # Check if incognito is enabled in config
        incognito_config = self.config.get("incognito", {})
        if not incognito_config.get("enabled", True):
            self.ui.console.print("[yellow]Incognito mode is disabled in configuration[/yellow]")
            self.incognito_mode = False
            return
        
        # Update ChatManager and ConversationManager incognito mode
        if self.chat_manager:
            self.chat_manager.set_incognito_mode(self.incognito_mode)
        if self.conversation_manager:
            self.conversation_manager.set_incognito_mode(self.incognito_mode)
        
        if self.incognito_mode:
            # Get incognito model display name
            model_info = incognito_config.get("model", {})
            model_display = model_info.get("display_name", "Local Model")
            self.ui.console.print(f"[bold magenta]🕶️  Incognito mode ON[/bold magenta] - Using {model_display}")
            self.ui.console.print("[dim]Conversations will not be saved in incognito mode[/dim]")
        else:
            current_model = self.model_manager.get_model_display_name(self.model_manager.current_model)
            self.ui.console.print(f"[bold cyan]👁️  Incognito mode OFF[/bold cyan] - Using {current_model}")
    
    def _compact_payload(self):
        """Compact all command output messages in the current payload"""
        if not self.chat_manager or not self.chat_manager.payload:
            self.ui.console.print("[yellow]No payload to compact[/yellow]")
            return
        
        compacted_count = 0
        
        for message in self.chat_manager.payload:
            if message.get("role") == "user" and "SYSTEM MESSAGE:" in message.get("content", ""):
                original_content = message["content"]
                compacted_content = self._truncate_system_message_outputs(original_content)
                
                if len(compacted_content) < len(original_content):
                    message["content"] = compacted_content
                    compacted_count += 1
        
        if compacted_count > 0:
            self.ui.console.print(f"[bold green]📦 Compacted {compacted_count} command output messages in payload[/bold green]")
            
            # Update conversation manager if available
            if self.conversation_manager:
                self.conversation_manager.update_payload(self.chat_manager.payload)
        else:
            self.ui.console.print("[yellow]No command output messages found to compact[/yellow]")
    
    def _handle_reset_config(self):
        """Handle the /resetconfig command to re-run setup wizard"""
        new_config = reset_config()
        if new_config:
            # Reload the configuration
            self.config = new_config
            
            # Re-initialize managers with new config
            self.model_manager = ModelManager(self.config)
            self.conversation_manager = ConversationManager(self.config, self.ui)
            self.web_search_manager = WebSearchManager(self.config)
            self.context_manager = ContextManager(self.config)
            self.chat_manager = ChatManager(self.config, self.model_manager, self.conversation_manager, self.web_search_manager, self.context_manager)
            self.terminal_input = TerminalInput(self.config)
            
            # Reload settings
            settings = self.config.get("settings", {})
            self.max_retries = settings.get("max_retries", 10)
            self.ai_mode = settings.get("default_mode", "ai").lower() == "ai"
            
            self.ui.console.print("[green]Configuration reloaded successfully![/green]")
    
    def _truncate_system_message_outputs(self, content: str, max_length: int = 500) -> str:
        """Truncate command outputs within system messages"""
        if not content or "Output:" not in content:
            return content
        
        lines = content.split('\n')
        result_lines = []
        in_output_section = False
        output_lines = []
        
        for line in lines:
            if line.startswith("Output:"):
                in_output_section = True
                output_lines = [line]
            elif in_output_section and (line.startswith("Success:") or line.startswith("Command output:") or line == ""):
                # End of output section
                output_text = '\n'.join(output_lines)
                if len(output_text) > max_length:
                    # Truncate the output
                    truncated_output = output_text[:max_length]
                    last_newline = truncated_output.rfind('\n')
                    
                    if last_newline > max_length * 0.7:
                        truncated_output = output_text[:last_newline]
                    
                    truncated_output += "\n... [truncated by /compact command]"
                    result_lines.append(truncated_output)
                else:
                    result_lines.extend(output_lines)
                
                in_output_section = False
                output_lines = []
                result_lines.append(line)
            elif in_output_section:
                output_lines.append(line)
            else:
                result_lines.append(line)
        
        # Handle case where output section continues to end of message
        if in_output_section and output_lines:
            output_text = '\n'.join(output_lines)
            if len(output_text) > max_length:
                truncated_output = output_text[:max_length]
                last_newline = truncated_output.rfind('\n')
                
                if last_newline > max_length * 0.7:
                    truncated_output = output_text[:last_newline]
                
                truncated_output += "\n... [truncated by /compact command]"
                result_lines.append(truncated_output)
            else:
                result_lines.extend(output_lines)
        
        return '\n'.join(result_lines)
    
    
    
    
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
        
        # Parse all block types from response
        command_pattern = re.compile(r"```command\s*(.*?)\s*```", re.DOTALL)
        websearch_pattern = re.compile(r"```websearch\s*(.*?)\s*```", re.DOTALL)
        distill_pattern = re.compile(r"```context_distill\s*(.*?)\s*```", re.DOTALL)
        prune_pattern = re.compile(r"```context_prune\s*(.*?)\s*```", re.DOTALL)
        untruncate_pattern = re.compile(r"```context_untruncate\s*(.*?)\s*```", re.DOTALL)
        
        commands = command_pattern.findall(response)
        websearches = websearch_pattern.findall(response)
        distills = distill_pattern.findall(response)
        prunes = prune_pattern.findall(response)
        untruncates = untruncate_pattern.findall(response)
        
        # Check for multiple actions (commands + searches + context ops)
        total_actions = len(commands) + len(websearches) + len(distills) + len(prunes) + len(untruncates)
        
        if total_actions > 1:
            self._handle_multiple_actions_response(total_actions)
        elif distills:
            self._handle_context_distill(response, distills)
        elif prunes:
            self._handle_context_prune(response, prunes)
        elif untruncates:
            self._handle_context_untruncate(response, untruncates)
        elif commands:
            self._handle_command_response(response, commands)
        elif websearches:
            self._handle_websearch_response(response, websearches)
        else:
            self._handle_text_response(response)
    
    def _handle_empty_response(self):
        """Handle empty AI response"""
        assert self.chat_manager is not None
        
        self.ui.console.print("[yellow]AI provided empty response - treating as task completion signal.[/yellow]")
        
        if self.original_request:
            msg = {
                "role": "user", 
                "content": f"SYSTEM MESSAGE: Task appears to be complete for: {self.original_request}. Please provide a brief summary of what was accomplished."
            }
            self.chat_manager.payload.append(msg)
            self.context_manager.assign_metadata(msg, label="Task completion prompt")
            self.rejudge = True
            self.original_request = ""
        else:
            msg = {
                "role": "user", 
                "content": "SYSTEM MESSAGE: You provided an empty response. Please provide a proper response or explain why you cannot proceed."
            }
            self.chat_manager.payload.append(msg)
            self.context_manager.assign_metadata(msg, label="Empty response handling")
            self.rejudge = True
    
    def _handle_multiple_actions_response(self, total_actions):
        """Handle response with multiple commands/searches/context operations"""
        assert self.chat_manager is not None
        
        self.ui.console.print(f"[red]Multiple actions detected ({total_actions} actions). Asking AI to correct.[/red]")
        msg = {
            "role": "user", 
            "content": f"SYSTEM MESSAGE: You provided {total_actions} action blocks in one response, which is forbidden. You must provide EXACTLY ONE command, search, or context management block per response. Please choose the FIRST action you need to take and provide it alone with explanation."
        }
        self.chat_manager.payload.append(msg)
        self.context_manager.assign_metadata(msg, label="Multiple actions error")
        self.rejudge = True
        self.rejudge_count += 1
        if self.rejudge_count > 3:
            self.ui.console.print(f"[red]Too many multiple action violations. Resetting conversation.[/red]")
            self.chat_manager.clear_history()
            self.context_manager.reset()
            self.rejudge = False
            self.rejudge_count = 0

    # ─── Context Management Handlers ───────────────────────────────────

    def _display_context_management_message(self, response):
        """Display the AI's message text from a context management response (stripping tool blocks)"""
        # Strip all context management blocks from the response
        display_text = re.sub(r"```context_distill\s*.*?\s*```", "", response, flags=re.DOTALL)
        display_text = re.sub(r"```context_prune\s*.*?\s*```", "", display_text, flags=re.DOTALL)
        display_text = re.sub(r"```context_untruncate\s*.*?\s*```", "", display_text, flags=re.DOTALL)
        display_text = self.chat_manager.strip_response_tags_for_display(display_text).strip()
        
        if display_text:
            md = Markdown(display_text)
            self.ui.console.print()
            self.ui.console.print(self.ui.ai_panel(md, border_style="dim"))
            self.ui.console.print()

    def _handle_context_distill(self, response, distill_blocks):
        """Handle response containing a context_distill block"""
        assert self.chat_manager is not None
        assert self.context_manager is not None
        
        self.rejudge_count = 0
        
        # Display the AI's accompanying message
        self._display_context_management_message(response)
        
        # Parse the distill block
        block_content = distill_blocks[0].strip()
        msg_id, summary = self._parse_context_distill(block_content)
        
        if msg_id is not None and summary:
            result = self.context_manager.distill(self.chat_manager.payload, msg_id, summary)
            if result:
                distilled_id, label = result
                self.ui.console.print(f"[dim]  ✓ Distilled #{distilled_id}: {label}[/dim]")
                # Inject continuation message
                msg = {"role": "user", "content": "SYSTEM MESSAGE: Context management applied. Continue with your task."}
                self.chat_manager.payload.append(msg)
                self.context_manager.assign_metadata(msg, label="Context management confirmation")
                self.rejudge = True
            else:
                self.ui.console.print(f"[dim yellow]  ✗ Could not distill message #{msg_id} (not found, already pruned, or not prunable)[/dim yellow]")
                msg = {"role": "user", "content": f"SYSTEM MESSAGE: Could not distill message #{msg_id}. It may not exist, may already be pruned, or is not a prunable message. Continue with your task."}
                self.chat_manager.payload.append(msg)
                self.context_manager.assign_metadata(msg, label="Context management error")
                self.rejudge = True
        else:
            self.ui.console.print(f"[dim yellow]  ✗ Invalid context_distill format[/dim yellow]")
            msg = {"role": "user", "content": "SYSTEM MESSAGE: Invalid context_distill format. Use: id: <number> and summary: <text>. Continue with your task."}
            self.chat_manager.payload.append(msg)
            self.context_manager.assign_metadata(msg, label="Context management error")
            self.rejudge = True
    
    def _handle_context_prune(self, response, prune_blocks):
        """Handle response containing a context_prune block"""
        assert self.chat_manager is not None
        assert self.context_manager is not None
        
        self.rejudge_count = 0
        
        # Display the AI's accompanying message
        self._display_context_management_message(response)
        
        # Parse the prune block
        block_content = prune_blocks[0].strip()
        msg_ids = self._parse_context_prune(block_content)
        
        if msg_ids:
            pruned_info = self.context_manager.prune(self.chat_manager.payload, msg_ids)
            if pruned_info:
                for pruned_id, label in pruned_info:
                    self.ui.console.print(f"[dim]  ✓ Pruned #{pruned_id}: {label}[/dim]")
                msg = {"role": "user", "content": "SYSTEM MESSAGE: Context management applied. Continue with your task."}
                self.chat_manager.payload.append(msg)
                self.context_manager.assign_metadata(msg, label="Context management confirmation")
                self.rejudge = True
            else:
                self.ui.console.print(f"[dim yellow]  ✗ No messages were pruned (IDs not found or already pruned)[/dim yellow]")
                msg = {"role": "user", "content": f"SYSTEM MESSAGE: Could not prune messages with IDs {msg_ids}. They may not exist or are already pruned. Continue with your task."}
                self.chat_manager.payload.append(msg)
                self.context_manager.assign_metadata(msg, label="Context management error")
                self.rejudge = True
        else:
            self.ui.console.print(f"[dim yellow]  ✗ Invalid context_prune format[/dim yellow]")
            msg = {"role": "user", "content": "SYSTEM MESSAGE: Invalid context_prune format. Use: ids: <id1>, <id2>, ... Continue with your task."}
            self.chat_manager.payload.append(msg)
            self.context_manager.assign_metadata(msg, label="Context management error")
            self.rejudge = True
    
    def _handle_context_untruncate(self, response, untruncate_blocks):
        """Handle response containing a context_untruncate block"""
        assert self.chat_manager is not None
        assert self.context_manager is not None
        
        self.rejudge_count = 0
        
        # Display the AI's accompanying message
        self._display_context_management_message(response)
        
        # Parse the untruncate block
        block_content = untruncate_blocks[0].strip()
        msg_id = self._parse_context_untruncate(block_content)
        
        if msg_id is not None:
            result = self.context_manager.untruncate(self.chat_manager.payload, msg_id)
            if result:
                untruncated_id, label = result
                self.ui.console.print(f"[dim]  ✓ Untruncated #{untruncated_id}: {label}[/dim]")
                msg = {"role": "user", "content": "SYSTEM MESSAGE: Message untruncated - full content is now visible. Continue with your task."}
                self.chat_manager.payload.append(msg)
                self.context_manager.assign_metadata(msg, label="Context management confirmation")
                self.rejudge = True
            else:
                self.ui.console.print(f"[dim yellow]  ✗ Could not untruncate message #{msg_id} (not truncated or not found)[/dim yellow]")
                msg = {"role": "user", "content": f"SYSTEM MESSAGE: Could not untruncate message #{msg_id}. It may not be truncated or does not exist. Continue with your task."}
                self.chat_manager.payload.append(msg)
                self.context_manager.assign_metadata(msg, label="Context management error")
                self.rejudge = True
        else:
            self.ui.console.print(f"[dim yellow]  ✗ Invalid context_untruncate format[/dim yellow]")
            msg = {"role": "user", "content": "SYSTEM MESSAGE: Invalid context_untruncate format. Use: id: <number>. Continue with your task."}
            self.chat_manager.payload.append(msg)
            self.context_manager.assign_metadata(msg, label="Context management error")
            self.rejudge = True

    # ─── Context Block Parsers ─────────────────────────────────────────

    def _parse_context_distill(self, block_content):
        """Parse context_distill block content. Returns (msg_id, summary) or (None, None)"""
        msg_id = None
        summary_lines = []
        in_summary = False
        
        for line in block_content.strip().split('\n'):
            stripped = line.strip()
            if stripped.lower().startswith('id:') and not in_summary:
                try:
                    msg_id = int(stripped.split(':', 1)[1].strip())
                except ValueError:
                    pass
            elif stripped.lower().startswith('summary:'):
                summary_lines.append(stripped.split(':', 1)[1].strip())
                in_summary = True
            elif in_summary:
                summary_lines.append(line.rstrip())
        
        summary = '\n'.join(summary_lines).strip()
        return msg_id, summary if summary else None
    
    def _parse_context_prune(self, block_content):
        """Parse context_prune block content. Returns list of message IDs"""
        for line in block_content.strip().split('\n'):
            stripped = line.strip()
            if stripped.lower().startswith('ids:'):
                ids_str = stripped.split(':', 1)[1].strip()
                try:
                    return [int(x.strip()) for x in ids_str.split(',') if x.strip()]
                except ValueError:
                    return []
            elif stripped.lower().startswith('id:'):
                # Also handle single id
                try:
                    return [int(stripped.split(':', 1)[1].strip())]
                except ValueError:
                    return []
        return []
    
    def _parse_context_untruncate(self, block_content):
        """Parse context_untruncate block content. Returns message ID or None"""
        for line in block_content.strip().split('\n'):
            stripped = line.strip()
            if stripped.lower().startswith('id:'):
                try:
                    return int(stripped.split(':', 1)[1].strip())
                except ValueError:
                    return None
        return None

    # ─── Command & Search Handlers ─────────────────────────────────────

    def _handle_command_response(self, response, commands):
        """Handle response containing commands"""
        assert self.chat_manager is not None
        
        # Process single command
        self.rejudge = False
        self.rejudge_count = 0
        
        # Display response (strip tags for display while keeping original in payload)
        display_response = self.chat_manager.strip_response_tags_for_display(response)
        md = Markdown(display_response)
        self.ui.console.print()
        self.ui.console.print(self.ui.ai_panel(md))
        self.ui.console.print()
        
        # Execute command
        command = commands[0].strip()
        if not command:
            self.ui.console.print("[yellow]Empty command block detected.[/yellow]")
            return
        
        self._execute_command_with_confirmation(command)

    def _handle_websearch_response(self, response, websearches):
        """Handle response containing web searches"""
        assert self.chat_manager is not None
        
        # Process single web search
        self.rejudge = False
        self.rejudge_count = 0
        
        # Display response (strip tags for display while keeping original in payload)
        display_response = self.chat_manager.strip_response_tags_for_display(response)
        md = Markdown(display_response)
        self.ui.console.print()
        self.ui.console.print(self.ui.ai_panel(md))
        self.ui.console.print()
        
        # Execute web search
        query = websearches[0].strip()
        if not query:
            self.ui.console.print("[yellow]Empty web search block detected.[/yellow]")
            return
        
        self._execute_web_search(query)
    
    def _handle_text_response(self, response):
        """Handle text-only response"""
        assert self.chat_manager is not None
        
        self.rejudge = False
        self.rejudge_count = 0
        
        # Display response (strip tags for display while keeping original in payload)
        display_response = self.chat_manager.strip_response_tags_for_display(response)
        md = Markdown(display_response)
        self.ui.console.print()
        self.ui.console.print(self.ui.ai_panel(md))
        self.ui.console.print()
        
        # Check if task completion is needed
        if self.original_request:
            self.conversation_history.append(f"AI Reply: {response}")
            
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
            
            # Check if this is a question requiring user input
            is_question = self.chat_manager.is_question(response)
            
            if is_question:
                # Send notification for questions
                self.chat_manager.send_system_notification(
                    "AI-Shell Question", 
                    "The AI has a question and needs your input"
                )
            elif not is_question:
                # Check if task is complete
                is_complete = self.chat_manager.is_complete(response)
                
                if is_complete:
                    # Reset auto-approve state when task is complete
                    self.auto_approve_commands = False
                    # Send notification for completion
                    self.chat_manager.send_system_notification(
                        "AI-Shell Complete", 
                        "The AI has completed the requested task"
                    )
                else:
                    msg = {"role": "user", "content": f"SYSTEM MESSAGE: The original request ({self.original_request}) is not yet complete. Please continue with the next step."}
                    self.chat_manager.payload.append(msg)
                    self.context_manager.assign_metadata(msg, label="Task continuation")
                    self.rejudge = True
    
    def _execute_command_with_confirmation(self, command):
        """Execute command after user confirmation, auto-approving safe read-only commands"""
        assert self.chat_manager is not None
        
        # Skip confirmation if auto-approve is enabled (user pressed 'a' earlier)
        if self.auto_approve_commands:
            self._execute_and_process_command(command)
            return
        
        # Auto-approve safe (read-only) commands without asking
        if self.safe_commands and is_safe_command(command, self.safe_commands):
            cmd_display = command if len(command) <= 80 else command[:77] + "..."
            self.ui.console.print(Panel(
                f"[bold white]Auto-executing safe command:[/bold white] [cyan]`{cmd_display}`[/cyan]",
                title="[green]Safe Command[/green]",
                border_style="green"
            ))
            self._execute_and_process_command(command)
            return
        
        # Ask for confirmation for non-safe commands
        panel_content = f"[bold white]Execute command:[/bold white] [cyan]`{command}`[/cyan]"
        self.ui.console.print(Panel(panel_content, title="[yellow]Command[/yellow]", border_style="yellow"))
        
        assert self.terminal_input is not None
        user_choice = self.terminal_input.get_confirmation("Execute? [Y/n/a]", "Y").lower()
        
        if user_choice in ["a", "all"]:
            self.auto_approve_commands = True
            self.ui.console.print("[green]Auto-approving all commands for this request[/green]")
            self._execute_and_process_command(command)
        elif user_choice == "n":
            reason = self.terminal_input.get_reason_input("Reason for decline")
            msg = {"role": "user", "content": f"SYSTEM MESSAGE: User declined to run the command: {command}\nReason: {reason}\n\nPlease provide an alternative approach to complete the original request: {self.original_request}"}
            self.chat_manager.payload.append(msg)
            cmd_label = command[:60] + "..." if len(command) > 60 else command
            self.context_manager.assign_metadata(msg, label=f"User declined: {cmd_label}")
            self.rejudge = True
        else:
            self._execute_and_process_command(command)
    
    def _execute_web_search(self, query):
        """Execute web search and process results"""
        assert self.chat_manager is not None
        assert self.web_search_manager is not None
        
        # Check if web search is available
        if not self.web_search_manager.is_available():
            self.ui.console.print("[red]Web search is not available. Please configure a search model in your config (e.g. perplexity/sonar-pro).[/red]")
            return
        
        # Display search query
        panel_content = f"[bold white]Web search query:[/bold white] [cyan]{query}[/cyan]"
        self.ui.console.print(Panel(panel_content, title="[cyan]Web Search[/cyan]", border_style="cyan"))
        
        # Execute the search
        search_response = self.web_search_manager.search(query)
        
        query_label = query[:60] + "..." if len(query) > 60 else query
        
        if search_response:
            # Format results but don't display them to the user
            formatted_results = self.web_search_manager.format_search_results(search_response)
            
            # Track conversation
            self.conversation_history.append(f"Web Search: {query}")
            self.conversation_history.append(f"Results: {formatted_results}")
            
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
            
            # Add search results to conversation context
            msg = {"role": "user", "content": f"SYSTEM MESSAGE: Web search executed for: {query}\n\nSearch Results:\n{formatted_results}"}
            self.chat_manager.payload.append(msg)
            self.context_manager.assign_metadata(msg, label=f"Web search: {query_label}")
            self.rejudge = True
        else:
            # Search failed
            self.ui.console.print("[red]Web search failed. Please try a different query or approach.[/red]")
            msg = {"role": "user", "content": f"SYSTEM MESSAGE: Web search failed for query: {query}\n\nPlease try a different approach or rephrase the search query."}
            self.chat_manager.payload.append(msg)
            self.context_manager.assign_metadata(msg, label=f"Web search failed: {query_label}")
            self.rejudge = True

    def _execute_and_process_command(self, command):
        """Execute command and process results"""
        assert self.chat_manager is not None
        assert self.context_manager is not None
        
        # Execute the command
        success, result = execute_command(command)
        
        # Auto-truncate long outputs
        truncated_result, was_truncated, original_result = self.context_manager.auto_truncate(result)
        
        if was_truncated:
            self.ui.console.print(f"[dim]  Output auto-truncated ({len(result)} chars → {len(truncated_result)} chars)[/dim]")
        
        # Track conversation
        self.conversation_history.append(f"Command: {command}")
        self.conversation_history.append(f"Output: {truncated_result}")
        self.conversation_history.append(f"Success: {success}")
        
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
        
        # Command label for context manager
        cmd_label = command[:60] + "..." if len(command) > 60 else command
        
        # Check task completion based on response type
        is_complete = self.chat_manager.is_complete(result)
        is_question = self.chat_manager.is_question(result)
        
        if is_question:
            # Send notification for questions
            self.chat_manager.send_system_notification(
                "AI-Shell Question", 
                "The AI has a question and needs your input"
            )
        
        if not is_complete:
            # Task needs more steps
            msg = {"role": "user", "content": f"SYSTEM MESSAGE: Command executed: {command}\nOutput: {truncated_result}\nSuccess: {success}\n\nThe original request is not yet complete. Please continue with the next step."}
            self.chat_manager.payload.append(msg)
            self.context_manager.assign_metadata(msg, label=f"Command output: {cmd_label}")
            
            # Store original for untruncate
            if was_truncated:
                full_content = f"SYSTEM MESSAGE: Command executed: {command}\nOutput: {original_result}\nSuccess: {success}\n\nThe original request is not yet complete. Please continue with the next step."
                msg["_state"] = "truncated"
                msg["_original_content"] = full_content
            
            self.rejudge = True
        else:
            # Task is complete - send notification
            self.chat_manager.send_system_notification(
                "AI-Shell Complete", 
                "The AI has completed the requested task"
            )
            # Reset auto-approve state when task is complete
            self.auto_approve_commands = False
            # Task is complete
            with self.ui.console.status("[bold green]Preparing summary...[/bold green]", spinner_style="green"):
                msg = {"role": "user", "content": f"SYSTEM MESSAGE: Task completed successfully. Command executed: {command}\nCommand output: {truncated_result}\nSuccess: {success}\n\nPlease provide a brief summary of what was accomplished based on the command output, or answer if the original request was a question."}
                self.chat_manager.payload.append(msg)
                self.context_manager.assign_metadata(msg, label=f"Command output: {cmd_label}")
                
                # Store original for untruncate
                if was_truncated:
                    full_content = f"SYSTEM MESSAGE: Task completed successfully. Command executed: {command}\nCommand output: {original_result}\nSuccess: {success}\n\nPlease provide a brief summary of what was accomplished based on the command output, or answer if the original request was a question."
                    msg["_state"] = "truncated"
                    msg["_original_content"] = full_content
            
            self.rejudge = True
            self.retry_count = 0
            self.original_request = ""
    
    def _handle_task_failure(self, command, result, success):
        """Handle task failure with retry logic"""
        assert self.chat_manager is not None
        
        cmd_label = command[:60] + "..." if len(command) > 60 else command
        
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            with self.ui.console.status("[bold yellow]Preparing retry...[/bold yellow]", spinner_style="yellow"):
                msg = {"role": "user", "content": f"SYSTEM MESSAGE: Command executed but task status check failed.\nCommand: {command}\nOutput: {result}\nSuccess: {success}\n\nPlease try a different approach to complete: {self.original_request}"}
                self.chat_manager.payload.append(msg)
                self.context_manager.assign_metadata(msg, label=f"Task failure: {cmd_label}")
            self.rejudge = True
        else:
            self.ui.console.print(f"[yellow]Maximum retry attempts ({self.max_retries}) reached.[/yellow]")
            assert self.terminal_input is not None
            retry_choice = self.terminal_input.get_confirmation("Do you want to continue trying? [Y/n]", "N").upper()
            if retry_choice == "Y":
                self.retry_count = 0
                with self.ui.console.status("[bold yellow]Preparing retry...[/bold yellow]", spinner_style="yellow"):
                    msg = {"role": "user", "content": f"SYSTEM MESSAGE: Command executed but failed.\nCommand: {command}\nOutput: {result}\nSuccess: {success}\n\nUser requested to continue trying. Please try a different approach to complete: {self.original_request}"}
                    self.chat_manager.payload.append(msg)
                    self.context_manager.assign_metadata(msg, label=f"Task failure retry: {cmd_label}")
                self.rejudge = True
            else:
                with self.ui.console.status("[bold red]Preparing summary...[/bold red]", spinner_style="red"):
                    msg = {"role": "user", "content": f"SYSTEM MESSAGE: Task failed after {self.max_retries} attempts and user chose to stop. Please provide a summary of what was attempted and suggest alternatives."}
                    self.chat_manager.payload.append(msg)
                    self.context_manager.assign_metadata(msg, label="Task stopped")
                self.rejudge = True
                self.retry_count = 0
