#!/usr/bin/env python

"""
Enhanced terminal input handler using prompt_toolkit for a real terminal experience.
Provides arrow key navigation, tab completion, proper line editing, and command history.
"""

import os
import sys
import tty
import html
import termios
import getpass
import socket
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


class InteractiveModelSelector:
    """Interactive model picker with arrow/jk navigation and / search."""

    def __init__(self, models: list, current_alias: str):
        """
        Args:
            models: List of dicts with keys: alias, display_name, api_name
            current_alias: The currently active model alias
        """
        self.all_models = models
        self.current_alias = current_alias
        self.filtered_models = list(models)
        self.selected_index = 0
        self.search_mode = False
        self.search_text = ""
        self.result = None  # Will hold selected alias or None

        # Pre-select the current model
        for i, m in enumerate(self.filtered_models):
            if m["alias"] == current_alias:
                self.selected_index = i
                break

    def _apply_filter(self):
        """Filter models by search text and reset selection."""
        q = self.search_text.lower()
        if not q:
            self.filtered_models = list(self.all_models)
        else:
            self.filtered_models = [
                m for m in self.all_models
                if q in m["alias"].lower()
                or q in m["display_name"].lower()
                or q in m["api_name"].lower()
            ]
        # Clamp selection
        if self.selected_index >= len(self.filtered_models):
            self.selected_index = max(0, len(self.filtered_models) - 1)

    def _get_list_content(self):
        """Return formatted text tuples for the model list."""
        fragments = []
        if not self.filtered_models:
            fragments.append(("class:ms.dim", "  No models match your search.\n"))
            return fragments

        for i, m in enumerate(self.filtered_models):
            is_selected = (i == self.selected_index)
            is_current = (m["alias"] == self.current_alias)
            marker = " ✓" if is_current else "  "

            if is_selected:
                style = "class:ms.selected"
                pointer = " ▸ "
            else:
                style = "class:ms.item"
                pointer = "   "

            line = f"{pointer}{m['display_name']}{marker}"
            # Pad to consistent width
            line = line.ljust(40)
            detail = f"  {m['alias']}  ({m['api_name']})"

            fragments.append((style, line))
            fragments.append(("class:ms.dim" if not is_selected else "class:ms.selected.dim", detail))
            fragments.append(("", "\n"))

        # Remove trailing newline
        if fragments and fragments[-1] == ("", "\n"):
            fragments.pop()

        return fragments

    def _get_header_content(self):
        """Return formatted text for the header bar."""
        return [
            ("class:ms.header", " Select Model "),
            ("class:ms.dim", "  ↑↓/jk: navigate  /: search  enter: select  esc: cancel\n"),
            ("class:ms.border", "─" * 70 + "\n"),
        ]

    def _get_search_content(self):
        """Return formatted text for the search bar."""
        if self.search_mode:
            return [
                ("class:ms.border", "─" * 70 + "\n"),
                ("class:ms.search.label", " / "),
                ("class:ms.search.text", self.search_text),
                ("class:ms.search.cursor", "█"),
            ]
        elif self.search_text:
            return [
                ("class:ms.border", "─" * 70 + "\n"),
                ("class:ms.dim", f" filter: {self.search_text}  "),
                ("class:ms.dim", "(/ to edit, esc to clear)"),
            ]
        return []

    def run(self) -> str | None:
        """Show the interactive selector. Returns selected alias or None."""
        from prompt_toolkit.application import Application
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.layout import Layout
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.styles import Style

        selector = self  # Reference for closures

        header_control = FormattedTextControl(lambda: selector._get_header_content())
        list_control = FormattedTextControl(lambda: selector._get_list_content())
        search_control = FormattedTextControl(lambda: selector._get_search_content())

        layout = Layout(HSplit([
            Window(header_control, height=2),
            Window(list_control, height=min(len(self.all_models), 20)),
            Window(search_control, height=3),
        ]))

        kb = KeyBindings()

        @kb.add("down")
        @kb.add("j", filter=Condition(lambda: not selector.search_mode))
        def move_down(event):
            if selector.filtered_models:
                selector.selected_index = (selector.selected_index + 1) % len(selector.filtered_models)

        @kb.add("up")
        @kb.add("k", filter=Condition(lambda: not selector.search_mode))
        def move_up(event):
            if selector.filtered_models:
                selector.selected_index = (selector.selected_index - 1) % len(selector.filtered_models)

        @kb.add("/", filter=Condition(lambda: not selector.search_mode))
        def enter_search(event):
            selector.search_mode = True

        @kb.add("escape")
        def on_escape(event):
            if selector.search_mode:
                # Exit search mode; if search is empty, clear filter
                selector.search_mode = False
                if not selector.search_text:
                    selector._apply_filter()
            else:
                # Cancel the selector
                selector.result = None
                event.app.exit()

        @kb.add("q", filter=Condition(lambda: not selector.search_mode))
        def on_quit(event):
            selector.result = None
            event.app.exit()

        @kb.add("enter")
        def on_enter(event):
            if selector.search_mode:
                # Apply search and return to navigation
                selector.search_mode = False
                selector._apply_filter()
            else:
                # Select the current model
                if selector.filtered_models:
                    selector.result = selector.filtered_models[selector.selected_index]["alias"]
                event.app.exit()

        @kb.add("backspace", filter=Condition(lambda: selector.search_mode))
        def on_backspace(event):
            if selector.search_text:
                selector.search_text = selector.search_text[:-1]
                selector._apply_filter()

        @kb.add("c-c")
        def on_ctrl_c(event):
            selector.result = None
            event.app.exit()

        # Catch all printable characters when in search mode
        @kb.add("<any>", filter=Condition(lambda: selector.search_mode))
        def on_search_char(event):
            char = event.data
            if char.isprintable() and len(char) == 1:
                selector.search_text += char
                selector._apply_filter()

        style = Style.from_dict({
            "ms.header": "#0066cc bold",
            "ms.border": "#333333",
            "ms.item": "",
            "ms.selected": "#ffffff bg:#0066cc bold",
            "ms.selected.dim": "#bbbbbb bg:#0066cc",
            "ms.dim": "#666666",
            "ms.search.label": "#0066cc bold",
            "ms.search.text": "#ffffff bold",
            "ms.search.cursor": "#0066cc",
        })

        app = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=False,
        )
        app.run()
        return selector.result


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
    
    # Variables that can be used in prompt section text
    PROMPT_VARIABLES = {
        '$model': 'Display name of the current AI model',
        '$dir': 'Current working directory (shortened)',
        '$mode': 'Current mode (AI, Direct, Incognito)',
        '$user': 'Current username',
        '$host': 'Hostname',
    }
    
    def __init__(self, config: dict):
        self.config = config
        self.settings = config.get("settings", {})
        self.prompt_config = config.get("prompt", {})
        
        # Setup history file
        history_dir = os.path.expanduser("~/.ai_shell")
        os.makedirs(history_dir, exist_ok=True)
        self.history_file = os.path.join(history_dir, "history")
        
        # Initialize components
        self.history = FileHistory(self.history_file)
        self.menu = CustomCommandMenu()
        self.completer = CustomCompleter(self.menu)
        
        # Build style dict (base styles + dynamic per-section styles)
        self.style = self._build_style()
    
    def _build_style(self) -> Style:
        """Build prompt_toolkit Style with dynamic per-section entries."""
        style_dict = {
            # Fallback prompt styles (used by confirmation/reason prompts)
            'prompt.ai': '#0066cc bold',
            'prompt.direct': '#00cc66 bold',
            'prompt.incognito': '#8b3fbb bold',
            'prompt.path': '#666666',
            # Completion menu styles
            'completion-menu.completion': 'noinherit',
            'completion-menu.completion.current': '#ffffff bg:#0066cc bold',
            'completion-menu.meta': 'noinherit',
            'completion': 'noinherit',
            'completion.current': '#ffffff bg:#0066cc bold',
            'scrollbar.background': 'hidden',
            'scrollbar.button': 'hidden',
            'scrollbar.arrow': 'hidden',
            'scrollbar': 'hidden',
            'completion-menu.scrollbar': 'hidden',
            'completion-menu.scrollbar.background': 'hidden',
            'completion-menu.scrollbar.button': 'hidden',
            'completion-menu.scrollbar.arrow': 'hidden',
        }
        
        # Generate styles for every section in every mode
        for mode_key in ('ai', 'direct', 'incognito'):
            sections = self.prompt_config.get(mode_key, [])
            for i, section in enumerate(sections):
                cls_name = f'ps.{mode_key}.{i}'
                fg = section.get('fg', '')
                bg = section.get('bg', '')
                parts = []
                if fg:
                    parts.append(fg)
                if bg:
                    parts.append(f'bg:{bg}')
                style_dict[cls_name] = ' '.join(parts) if parts else ''
        
        return Style.from_dict(style_dict)
    
    def _substitute_variables(self, text: str, variables: dict) -> str:
        """Replace $variable placeholders in text with actual values."""
        result = text
        for var_name, var_value in variables.items():
            result = result.replace(var_name, var_value)
        return result
    
    def _build_prompt(self, mode_key: str, variables: dict) -> HTML:
        """Build an HTML prompt from configured sections for the given mode.
        
        Args:
            mode_key: One of 'ai', 'direct', 'incognito'
            variables: Dict mapping variable names ($model, $dir, etc.) to values
        
        Returns:
            prompt_toolkit HTML formatted text
        """
        sections = self.prompt_config.get(mode_key, [])
        html_parts = []
        
        for i, section in enumerate(sections):
            raw_text = section.get('text', '')
            display_text = self._substitute_variables(raw_text, variables)
            # Escape HTML special chars in the display text
            safe_text = html.escape(display_text)
            cls_name = f'ps.{mode_key}.{i}'
            html_parts.append(f'<{cls_name}>{safe_text}</{cls_name}>')
        
        return HTML(''.join(html_parts))
    
    def get_input(self, ai_mode: bool, model_name: str = "", incognito_mode: bool = False) -> str:
        """Get user input with custom command menu"""
        current_dir = get_prompt_directory()
        
        # Determine mode key and mode label
        if incognito_mode:
            mode_key = 'incognito'
            mode_label = 'Incognito'
        elif ai_mode:
            mode_key = 'ai'
            mode_label = 'AI'
        else:
            mode_key = 'direct'
            mode_label = 'Direct'
        
        # Build variable substitution map
        variables = {
            '$model': model_name,
            '$dir': current_dir,
            '$mode': mode_label,
            '$user': getpass.getuser(),
            '$host': socket.gethostname(),
        }
        
        # Build the prompt from config sections
        prompt_text = self._build_prompt(mode_key, variables)
        
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

    def interactive_model_select(self, models: list, current_alias: str) -> str | None:
        """Show an interactive model picker.
        
        Args:
            models: List of dicts with keys: alias, display_name, api_name
            current_alias: The currently active model alias
        
        Returns:
            Selected model alias, or None if cancelled.
        """
        selector = InteractiveModelSelector(models, current_alias)
        return selector.run()
