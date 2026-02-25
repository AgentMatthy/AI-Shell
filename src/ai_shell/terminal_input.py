#!/usr/bin/env python

"""
Enhanced terminal input handler using prompt_toolkit for a real terminal experience.
Provides arrow key navigation, tab completion, proper line editing, and command history.
"""

import os
import sys
import tty
import termios
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import HSplit, Window, ConditionalContainer
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.dimension import Dimension

from .commands import get_prompt_directory


class CustomCommandMenu:
    """Custom command menu that appears below the prompt"""
    
    def __init__(self):
        self.commands = {
            '/exit': 'Exit the AI Shell',
            '/quit': 'Exit the AI Shell',
            '/clear': 'Clear conversation history and start fresh',
            '/new': 'Clear conversation history and start fresh',
            '/reset': 'Clear conversation history and start fresh',
            '/help': 'Show help information',
            '/payload': 'Display current conversation payload',
            '/save': 'Save current conversation',
            '/load': 'Load a saved conversation',
            '/conversations': 'List all saved conversations (use -r to remove)',
            '/cv': 'List all saved conversations (use -r to remove)',
            '/archive': 'Archive current conversation',
            '/delete': 'Delete a saved conversation',
            '/status': 'Show conversation status',
            '/models': 'List available models',
            '/model': 'Switch to a different model',
            '/ai': 'Switch to AI mode',
            '/dr': 'Switch to Direct mode',
            '/inc': 'Toggle incognito mode',
            '/compact': 'Compact command outputs in current payload',
            '/recent': 'List recent conversations',
            '/r': 'List recent conversations'
        }
        self.filtered_commands = []
        self.selected_index = 0
        self.visible = False
    
    def filter_commands(self, query):
        """Filter commands based on query"""
        if not query or query == '/':
            self.filtered_commands = list(self.commands.items())
        else:
            query_lower = query.lower()
            self.filtered_commands = [
                (cmd, desc) for cmd, desc in self.commands.items()
                if cmd.lower().startswith(query_lower)
            ]
        
        # Reset selection if current selection is out of bounds
        if self.selected_index >= len(self.filtered_commands):
            self.selected_index = 0
    
    def move_selection(self, direction):
        """Move selection up (-1) or down (1)"""
        if not self.filtered_commands:
            return
        self.selected_index = (self.selected_index + direction) % len(self.filtered_commands)
    
    def get_selected_command(self):
        """Get currently selected command"""
        if self.filtered_commands and 0 <= self.selected_index < len(self.filtered_commands):
            return self.filtered_commands[self.selected_index][0]
        return None
    
    def get_menu_content(self):
        """Get formatted menu content"""
        if not self.visible or not self.filtered_commands:
            return ""
        
        lines = []
        for i, (cmd, desc) in enumerate(self.filtered_commands):
            if i == self.selected_index:
                # Selected item with highlight
                lines.append(('class:menu-selected', f"{cmd} - {desc}"))
            else:
                # Regular item
                lines.append(('class:menu-item', f"{cmd} - {desc}"))
            lines.append(('', '\n'))
        
        # Remove last newline
        if lines and lines[-1] == ('', '\n'):
            lines.pop()
        
        return lines


class CustomCompleter(Completer):
    """Custom completer that shows persistent command menu"""
    
    def __init__(self, menu):
        self.menu = menu
    
    def get_completions(self, document, complete_event):
        """Generate completions that persist"""
        text = document.text_before_cursor
        
        if text.startswith('/'):
            self.menu.filter_commands(text)
            
            # Return all filtered commands - let prompt_toolkit handle selection
            for cmd, desc in self.menu.filtered_commands:
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=f"{cmd} - {desc}",
                )
        else:
            # Hide menu when not typing commands
            pass


class TerminalInput:
    """Enhanced terminal input handler with custom command menu"""
    
    def __init__(self, config: dict):
        self.config = config
        self.settings = config.get("settings", {})
        
        # Setup history file
        history_dir = os.path.expanduser("~/.ai_shell")
        os.makedirs(history_dir, exist_ok=True)
        self.history_file = os.path.join(history_dir, "history")
        
        # Initialize components
        self.history = FileHistory(self.history_file)
        self.menu = CustomCommandMenu()
        self.completer = CustomCompleter(self.menu)
        
        # Define style for prompts and menu with transparent background
        self.style = Style.from_dict({
            'prompt.ai': '#0066cc bold',
            'prompt.direct': '#00cc66 bold',
            'prompt.incognito': '#8b3fbb bold',
            'prompt.path': '#666666',
            # Completely transparent completion menu - inherit terminal background
            'completion-menu.completion': 'noinherit',  # Don't inherit any background
            'completion-menu.completion.current': '#ffffff bg:#0066cc bold',  # Only selected has background
            'completion-menu.meta': 'noinherit',  # No styling
            'completion': 'noinherit',  # No background
            'completion.current': '#ffffff bg:#0066cc bold',
            # Multiple attempts to hide scrollbar with different class names
            'scrollbar.background': 'hidden',
            'scrollbar.button': 'hidden', 
            'scrollbar.arrow': 'hidden',
            'scrollbar': 'hidden',
            'completion-menu.scrollbar': 'hidden',
            'completion-menu.scrollbar.background': 'hidden',
            'completion-menu.scrollbar.button': 'hidden',
            'completion-menu.scrollbar.arrow': 'hidden',
        })
    
    def get_input(self, ai_mode: bool, model_name: str = "", incognito_mode: bool = False) -> str:
        """Get user input with custom command menu"""
        current_dir = get_prompt_directory()
        
        # Build prompt message
        if incognito_mode:
            prompt_text = HTML(
                f'<prompt.incognito>AI Shell [Incognito - {model_name}] </prompt.incognito>'
                f'<prompt.path>{current_dir}</prompt.path>'
                f'<prompt.incognito> > </prompt.incognito>'
            )
        elif ai_mode:
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
        
        # Custom key bindings - minimal to not interfere with default navigation
        kb = KeyBindings()
        
        @kb.add('escape')
        def hide_menu(event):
            """Hide menu"""
            pass  # Let default completion behavior handle this
        
        @kb.add('enter')
        def submit_on_enter(event):
            """Enter submits the prompt"""
            event.current_buffer.validate_and_handle()
        
        @kb.add('escape', 'enter')
        def newline_on_alt_enter(event):
            """Alt+Enter inserts a newline"""
            event.current_buffer.insert_text('\n')
        
        try:
            user_input = prompt(
                prompt_text,
                history=self.history,
                completer=self.completer,
                complete_style=CompleteStyle.COLUMN,  # Single column layout
                style=self.style,
                key_bindings=kb,
                wrap_lines=True,
                multiline=True,
                vi_mode=self.settings.get("vi_mode", False),
            )
            return user_input.strip()
        except (KeyboardInterrupt, EOFError):
            raise
    
    def get_confirmation(self, message: str, default: str = "y") -> str:
        """Get confirmation input with simpler prompt"""
        try:
            result = prompt(
                HTML(f'<prompt.ai>{message}</prompt.ai>'),
                style=self.style
            ).strip()
            return result if result else default
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
    def get_confirmation(self, message: str, default: str = "y") -> str:
        """Get confirmation input with simpler prompt"""
        try:
            result = prompt(
                HTML(f'<prompt.ai>{message}</prompt.ai>'),
                style=self.style
            ).strip()
            return result if result else default
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
    
    def get_confirmation(self, message: str, default: str = "y") -> str:
        """Get confirmation input with simpler prompt"""
        try:
            result = prompt(
                HTML(f'<prompt.ai>{message}</prompt.ai>'),
                style=self.style
            ).strip()
            # Return default if empty input
            return result if result else default
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
    
    def get_instant_confirmation(self) -> str:
        """Get instant Y/n/a confirmation via single keypress (no Enter needed).
        Returns 'y', 'n', or 'a'."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
        if ch in ('n', 'N'):
            return 'n'
        elif ch in ('a', 'A'):
            return 'a'
        else:
            # Y, Enter, or any other key = accept
            return 'y'
