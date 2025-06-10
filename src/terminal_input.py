#!/usr/bin/env python

"""
Enhanced terminal input handler using prompt_toolkit for a real terminal experience.
Provides arrow key navigation, tab completion, proper line editing, and command history.
"""

import os
from typing import List, Optional, Callable
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style

from .commands import get_prompt_directory


class AIShellCompleter(Completer):
    """Custom completer for AI shell commands and file paths"""
    
    def __init__(self):
        # Define AI shell commands
        self.ai_commands = [
            '/exit', '/quit', '/clear', '/new', '/reset', '/help',
            '/payload', '/save', '/load', '/conversations', '/cv',
            '/archive', '/delete', '/status', '/models', '/model',
            '/ai', '/dr'
        ]
    
    def get_completions(self, document, complete_event):
        """Generate completions for the current input"""
        text = document.text_before_cursor
        word = document.get_word_before_cursor()
        
        # Complete AI shell commands
        if text.startswith('/'):
            for cmd in self.ai_commands:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))
        
        # Complete file paths for regular commands
        elif word and ('/' in word or not text.strip().startswith('/')):
            # Get directory to search in
            if '/' in word:
                dir_path = os.path.dirname(word)
                if not dir_path:
                    dir_path = '.'
                file_prefix = os.path.basename(word)
            else:
                dir_path = '.'
                file_prefix = word
            
            try:
                # List files/directories matching the prefix
                if os.path.isdir(dir_path):
                    for item in os.listdir(dir_path):
                        if item.startswith(file_prefix):
                            full_path = os.path.join(dir_path, item) if dir_path != '.' else item
                            if os.path.isdir(full_path):
                                display = f"{item}/"
                            else:
                                display = item
                            yield Completion(display, start_position=-len(file_prefix))
            except (OSError, PermissionError):
                # Skip completion if we can't read the directory
                pass


class TerminalInput:
    """Enhanced terminal input handler with prompt_toolkit"""
    
    def __init__(self, config: dict):
        self.config = config
        self.settings = config.get("settings", {})
        
        # Setup history file
        history_dir = os.path.expanduser("~/.ai_shell")
        os.makedirs(history_dir, exist_ok=True)
        self.history_file = os.path.join(history_dir, "history")
        
        # Initialize components
        self.completer = AIShellCompleter()
        self.history = FileHistory(self.history_file)
        
        # Define style for prompts
        self.style = Style.from_dict({
            'prompt.ai': '#0066cc bold',
            'prompt.direct': '#00cc66 bold', 
            'prompt.path': '#666666',
            'completion-menu.completion': 'bg:#008888 #ffffff',
            'completion-menu.completion.current': 'bg:#00aaaa #000000',
        })
    
    def get_input(self, ai_mode: bool, model_name: str = "") -> str:
        """
        Get user input with enhanced terminal features
        
        Args:
            ai_mode: Whether in AI mode or direct mode
            model_name: Current model name for display
            
        Returns:
            User input string
        """
        current_dir = get_prompt_directory()
        
        # Build prompt message
        if ai_mode:
            prompt_text = HTML(
                f'<prompt.ai>AI Shell [AI - {model_name}] </prompt.ai>'
                f'<prompt.path>{current_dir}</prompt.path>'
                f'<prompt.ai> > </prompt.ai>'
            )
        else:
            prompt_text = HTML(
                f'<prompt.direct>AI Shell [Direct] </prompt.direct>'
                f'<prompt.path>{current_dir}</prompt.path>'
                f'<prompt.direct> > </prompt.direct>'
            )
        
        try:
            # Get input with all the enhanced features
            user_input = prompt(
                prompt_text,
                history=self.history,
                completer=self.completer,
                complete_style=CompleteStyle.MULTI_COLUMN,
                style=self.style,
                mouse_support=True,
                wrap_lines=True,
                multiline=False,
                vi_mode=self.settings.get("vi_mode", False),
            )
            return user_input.strip()
            
        except (KeyboardInterrupt, EOFError):
            # Re-raise these exceptions to be handled by the main app
            raise
    
    def get_confirmation(self, message: str, default: str = "y") -> str:
        """Get confirmation input with simpler prompt"""
        try:
            return prompt(
                HTML(f'<prompt.ai>{message}</prompt.ai>'),
                style=self.style,
                default=default
            ).strip()
        except (KeyboardInterrupt, EOFError):
            raise
    
    def get_reason_input(self, prompt_text: str) -> str:
        """Get reason/explanation input"""
        try:
            return prompt(
                HTML(f'<prompt.ai>{prompt_text}: </prompt.ai>'),
                style=self.style,
                history=self.history,
                multiline=False
            ).strip()
        except (KeyboardInterrupt, EOFError):
            raise
