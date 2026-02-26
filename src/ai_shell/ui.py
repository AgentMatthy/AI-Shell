#!/usr/bin/env python

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.box import Box

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
    def __init__(self):
        self.console = Console()
    
    def show_welcome(self):
        """Display welcome message"""
        welcome_text = """
[bold cyan]AI Shell Assistant[/bold cyan]
Type your requests and I'll help you execute commands.

[yellow]Available commands:[/yellow]
• [green]/help[/green] - Show this help message
• [green]/models[/green] - List available models  
• [green]/switch <model>[/green] - Switch to a different model
• [green]/clear[/green] - Clear conversation history
• [green]/exit[/green] or [green]/quit[/green] - Exit the program

[yellow]Modes:[/yellow]
• [blue]Question mode[/blue]: Ask questions (ends with ? or starts with question words)
• [blue]Command mode[/blue]: Request actions that will execute commands

[dim]Type your message and press Enter...[/dim]
        """
        
        panel = Panel(
            welcome_text,
            title="Welcome",
            border_style="blue"
        )
        self.console.print(panel)
    
    def show_help(self):
        """Display help information"""
        help_text = """
[bold cyan]AI Shell Assistant Help[/bold cyan]

[yellow]How to use:[/yellow]
• Type natural language requests for tasks you want to accomplish
• The AI will generate and execute appropriate shell commands
• You can ask questions by ending with '?' or using question words

[yellow]Examples:[/yellow]
• "List all Python files in this directory"
• "What is the current disk usage?"
• "Create a new directory called 'projects'"
• "Install the requests library using pip"
• "Show me the git status"

[yellow]General Commands:[/yellow]
• [green]/help[/green] - Show this help message
• [green]/models[/green] - List all available models
• [green]/model <alias>[/green] - Switch to a different model
• [green]/clear[/green] - Clear conversation history
• [green]/ai[/green] - Switch to AI mode
• [green]/dr[/green] - Switch to direct mode
• [green]/inc[/green] - Toggle incognito mode (private, local model)
• [green]/compact[/green] - Compact command outputs in current payload (truncate long outputs)
• [green]/resetconfig[/green] - Re-run the setup wizard to reconfigure AI Shell
• [green]/p[/green] - Show conversation payload
• [green]/exit[/green] or [green]/quit[/green] - Exit the program

[yellow]Incognito Mode:[/yellow]
• [magenta]/inc[/magenta] - Toggle incognito mode on/off
• Uses local model (default: Ollama) for privacy
• Conversations are not saved or stored
• Purple prompt indicates incognito mode is active
• Perfect for sensitive or private conversations

        [yellow]Conversation Management:[/yellow]
• [green]/save[/green] - Save current conversation (will prompt for name)
• [green]/save <n>[/green] - Save current conversation with specific name
• [green]/load[/green] - Load a saved conversation (will show list)
• [green]/load <n>[/green] - Load specific conversation by name or index
• [green]/conversations[/green] or [green]/conversation[/green] or [green]/cv[/green] - List all conversations (recent and saved)
• [green]/conversations -r[/green] or [green]/cv -r[/green] - Remove/delete a saved conversation
• [green]/recent[/green] or [green]/r[/green] - List recent conversations only
• [green]/archive[/green] - Archive current conversation and start fresh
• [green]/delete <n>[/green] - Delete a saved conversation
• [green]/status[/green] - Show current conversation status

[yellow]Tips:[/yellow]
• Be specific in your requests for better results
• The AI will ask for confirmation before running commands
• You can interrupt command execution with Ctrl+C
• Conversations auto-save every 5 interactions
• Previous conversations resume automatically on startup

[yellow]Prompt Customization:[/yellow]
• Edit the 'prompt' section in ~/.config/ai-shell/config.yaml
• Define sections for each mode: ai, direct, incognito
• Each section has: text, fg (text color), bg (background color)
• Available variables: [green]$model[/green], [green]$dir[/green], [green]$mode[/green], [green]$user[/green], [green]$host[/green]
        """
        
        panel = Panel(
            help_text,
            title="Help",
            border_style="green"
        )
        self.console.print(panel)
    
    def get_user_input(self, prompt_text="You", show_directory=True):
        """Get user input with a styled prompt"""
        if show_directory:
            from .commands import get_prompt_directory
            current_dir = get_prompt_directory()
            return Prompt.ask(f"[bold blue]{prompt_text}[/bold blue] [dim cyan]{current_dir}[/dim cyan]")
        else:
            return Prompt.ask(f"[bold blue]{prompt_text}[/bold blue]")
    
    def show_ai_response(self, response, title="AI Assistant"):
        """Display AI response in a styled panel"""
        panel = self.ai_panel(response)
        self.console.print(panel)
    
    def ai_panel(self, content, border_style="green", style="on grey11"):
        """Create a styled panel for AI messages — green line on left, subtle background"""
        return Panel(
            content,
            box=AI_MSG_BOX,
            border_style=border_style,
            style=style,
            padding=(0, 1),
        )
    
    def show_command_execution(self, command):
        """Display command being executed"""
        command_text = Text(f"$ {command}", style="bold yellow")
        panel = Panel(
            command_text,
            title="Executing Command",
            title_align="left",
            border_style="yellow"
        )
        self.console.print(panel)
    
    def show_task_status(self, completed, reason):
        """Display task completion status"""
        if completed:
            status_text = f"[green]✓ Task completed successfully[/green]\n{reason}"
            border_style = "green"
        else:
            status_text = f"[red]✗ Task may not have completed[/red]\n{reason}"
            border_style = "red"
        
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
            f"[red]{error_message}[/red]",
            title="Error",
            title_align="left",
            border_style="red"
        )
        self.console.print(panel)
    
    def show_warning(self, warning_message):
        """Display warning message"""
        panel = Panel(
            f"[yellow]{warning_message}[/yellow]",
            title="Warning",
            title_align="left",
            border_style="yellow"
        )
        self.console.print(panel)
    
    def show_info(self, info_message):
        """Display info message"""
        self.console.print(f"[cyan]{info_message}[/cyan]")
    
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
        
        self.console.print("\n[bold cyan]Previous conversation:[/bold cyan]")
        
        for message in display_messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            
            if role == "user":
                # Display user messages as plain text
                self.console.print(f"\n[bold green]You:[/bold green]")
                self.console.print(f"[white]{content}[/white]")
            elif role == "assistant":
                # Display assistant messages with left-line panel
                from rich.markdown import Markdown
                self.console.print(f"\n[bold blue]Assistant:[/bold blue]")
                md = Markdown(content)
                self.console.print(self.ai_panel(md))
        
        self.console.print(f"\n[dim]--- End of previous conversation ({len(display_messages)} messages) ---[/dim]\n")
