#!/usr/bin/env python

from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.box import Box

from .theme import create_console, get_theme

# Custom box with only a left vertical line (for AI messages)
# Line extends through top/bottom padding rows
AI_MSG_BOX = Box(
    "▎   \n"
    "▎   \n"
    "▎   \n"
    "▎   \n"
    "▎   \n"
    "▎   \n"
    "▎   \n"
    "▎   \n"
)

class UIManager:
    def __init__(self, config=None):
        self.theme = get_theme(config or {})
        self.console = create_console(config)
        # Keep raw color values handy for border_style / style params
        self._t = self.theme
    
    def show_welcome(self):
        """Display welcome message"""
        welcome_text = """
[bold accent]AI Shell Assistant[/bold accent]
Type your requests and I'll help you execute commands.

[warning]Available commands:[/warning]
• [accent_alt]/help[/accent_alt] - Show this help message
• [accent_alt]/models[/accent_alt] - List available models  
• [accent_alt]/switch <model>[/accent_alt] - Switch to a different model
• [accent_alt]/clear[/accent_alt] - Clear conversation history
• [accent_alt]/exit[/accent_alt] or [accent_alt]/quit[/accent_alt] - Exit the program

[warning]Modes:[/warning]
• [accent]Question mode[/accent]: Ask questions (ends with ? or starts with question words)
• [accent]Command mode[/accent]: Request actions that will execute commands

[muted]Type your message and press Enter...[/muted]
        """
        
        panel = Panel(
            welcome_text,
            title="Welcome",
            border_style=self._t["accent"]
        )
        self.console.print(panel)
    
    def show_help(self):
        """Display help information"""
        help_text = f"""
[bold accent]AI Shell Assistant Help[/bold accent]

[warning]How to use:[/warning]
• Type natural language requests for tasks you want to accomplish
• The AI will generate and execute appropriate shell commands
• You can ask questions by ending with '?' or using question words

[warning]Examples:[/warning]
• "List all Python files in this directory"
• "What is the current disk usage?"
• "Create a new directory called 'projects'"
• "Install the requests library using pip"
• "Show me the git status"

[warning]General Commands:[/warning]
• [accent_alt]/help[/accent_alt] - Show this help message
• [accent_alt]/models[/accent_alt] - List all available models
• [accent_alt]/model <alias>[/accent_alt] - Switch to a different model
• [accent_alt]/clear[/accent_alt] - Clear conversation history
• [accent_alt]/ai[/accent_alt] - Switch to AI mode
• [accent_alt]/dr[/accent_alt] - Switch to direct mode
• [accent_alt]/inc[/accent_alt] - Toggle incognito mode (private, local model)
• [accent_alt]/compact[/accent_alt] - Compact command outputs in current payload (truncate long outputs)
• [accent_alt]/resetconfig[/accent_alt] - Re-run the setup wizard to reconfigure AI Shell
• [accent_alt]/p[/accent_alt] - Show conversation payload
• [accent_alt]/exit[/accent_alt] or [accent_alt]/quit[/accent_alt] - Exit the program

[warning]Incognito Mode:[/warning]
• [accent_alt]/inc[/accent_alt] - Toggle incognito mode on/off
• Uses local model (default: Ollama) for privacy
• Conversations are not saved or stored
• Perfect for sensitive or private conversations

        [warning]Conversation Management:[/warning]
• [accent_alt]/save[/accent_alt] - Save current conversation (will prompt for name)
• [accent_alt]/save <n>[/accent_alt] - Save current conversation with specific name
• [accent_alt]/load[/accent_alt] - Load a saved conversation (will show list)
• [accent_alt]/load <n>[/accent_alt] - Load specific conversation by name or index
• [accent_alt]/conversations[/accent_alt] or [accent_alt]/conversation[/accent_alt] or [accent_alt]/cv[/accent_alt] - List all conversations (recent and saved)
• [accent_alt]/conversations -r[/accent_alt] or [accent_alt]/cv -r[/accent_alt] - Remove/delete a saved conversation
• [accent_alt]/recent[/accent_alt] or [accent_alt]/r[/accent_alt] - List recent conversations only
• [accent_alt]/archive[/accent_alt] - Archive current conversation and start fresh
• [accent_alt]/delete <n>[/accent_alt] - Delete a saved conversation
• [accent_alt]/status[/accent_alt] - Show current conversation status

[warning]Tips:[/warning]
• Be specific in your requests for better results
• The AI will ask for confirmation before running commands
• You can interrupt command execution with Ctrl+C
• Conversations auto-save every 5 interactions
• Previous conversations resume automatically on startup

[warning]Prompt Customization:[/warning]
• Edit the 'prompt' section in ~/.config/ai-shell/config.yaml
• Define sections for each mode: ai, direct, incognito
• Each section has: text, fg (text color), bg (background color)
• Available variables: [accent_alt]$model[/accent_alt], [accent_alt]$dir[/accent_alt], [accent_alt]$mode[/accent_alt], [accent_alt]$user[/accent_alt], [accent_alt]$host[/accent_alt]
        """
        
        panel = Panel(
            help_text,
            title="Help",
            border_style=self._t["accent_alt"]
        )
        self.console.print(panel)
    
    def get_user_input(self, prompt_text="You", show_directory=True):
        """Get user input with a styled prompt"""
        if show_directory:
            from .commands import get_prompt_directory
            current_dir = get_prompt_directory()
            return Prompt.ask(f"[bold accent]{prompt_text}[/bold accent] [muted]{current_dir}[/muted]")
        else:
            return Prompt.ask(f"[bold accent]{prompt_text}[/bold accent]")
    
    def show_ai_response(self, response, title="AI Assistant"):
        """Display AI response in a styled panel"""
        panel = self.ai_panel(response)
        self.console.print(panel)
    
    def ai_panel(self, content, border_style=None, style=None):
        """Create a styled panel for AI messages — accent line on left, block background"""
        return Panel(
            content,
            box=AI_MSG_BOX,
            border_style=border_style or self._t["muted"],
            style=style or f"on {self._t['block']}",
            padding=(0, 1),
        )
    
    def show_command_execution(self, command):
        """Display command being executed"""
        command_text = Text(f"$ {command}", style=f"bold {self._t['warning']}")
        panel = Panel(
            command_text,
            title="Executing Command",
            title_align="left",
            border_style=self._t["warning"]
        )
        self.console.print(panel)
    
    def show_task_status(self, completed, reason):
        """Display task completion status"""
        if completed:
            status_text = f"[success]✓ Task completed successfully[/success]\n{reason}"
            border_style = self._t["success"]
        else:
            status_text = f"[error]✗ Task may not have completed[/error]\n{reason}"
            border_style = self._t["error"]
        
        panel = Panel(
            status_text,
            title="Task Status",
            title_align="left",
            border_style=border_style
        )
        self.console.print(panel)
    
    def show_error(self, error_message):
        """Display error message"""
        panel = Panel(
            f"[error]{error_message}[/error]",
            title="Error",
            title_align="left",
            border_style=self._t["error"]
        )
        self.console.print(panel)
    
    def show_warning(self, warning_message):
        """Display warning message"""
        panel = Panel(
            f"[warning]{warning_message}[/warning]",
            title="Warning",
            title_align="left",
            border_style=self._t["warning"]
        )
        self.console.print(panel)
    
    def show_info(self, info_message):
        """Display info message"""
        self.console.print(f"[accent]{info_message}[/accent]")
    
    def display_conversation_messages(self, payload):
        """Display conversation messages in a readable format"""
        if not payload:
            return
        
        # Skip system messages and internal system messages for display
        display_messages = []
        for msg in payload:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            # Skip system role messages
            if role == "system":
                continue
            
            # Skip user messages that are actually system-generated (start with "SYSTEM MESSAGE:")
            if role == "user" and content.startswith("SYSTEM MESSAGE:"):
                continue
            
            display_messages.append(msg)
        
        if not display_messages:
            return
        
        self.console.print("\n[bold accent]Previous conversation:[/bold accent]")
        
        for message in display_messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            
            if role == "user":
                # Display user messages as plain text
                self.console.print(f"\n[bold accent_alt]You:[/bold accent_alt]")
                self.console.print(f"[fg]{content}[/fg]")
            elif role == "assistant":
                # Display assistant messages with left-line panel
                from rich.markdown import Markdown
                self.console.print(f"\n[bold accent]Assistant:[/bold accent]")
                md = Markdown(content)
                self.console.print(self.ai_panel(md))
        
        self.console.print(f"\n[muted]--- End of previous conversation ({len(display_messages)} messages) ---[/muted]\n")
