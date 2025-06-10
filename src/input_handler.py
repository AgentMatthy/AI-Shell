#!/usr/bin/env python

import subprocess
from rich.panel import Panel

from .commands import execute_command


class InputHandler:
    """Handles user input processing and command routing"""
    
    def __init__(self, config, ui, model_manager, conversation_manager, chat_manager):
        self.config = config
        self.ui = ui
        self.model_manager = model_manager
        self.conversation_manager = conversation_manager
        self.chat_manager = chat_manager
        self.settings = config.get("settings", {})
    
    def handle_input(self, user_input, ai_mode):
        """
        Process user input and return appropriate action
        
        Returns:
            str: Action to take - "exit", "continue", "switch_ai", "switch_direct", 
                 "direct_command", "process_ai"
        """
        if not user_input:
            return "continue"
        
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
        if not ai_mode:
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
            
            self.ui.console.print(f"\n[bold {role_color}][{i+1}] {message['role'].upper()}:[/bold {role_color}]")
            content = message["content"]
            truncate_length = self.settings.get("payload_truncate_length", 500)
            if len(content) > truncate_length:
                content = content[:truncate_length] + "... [truncated]"
            self.ui.console.print(Panel(content, border_style=role_color))
        
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
