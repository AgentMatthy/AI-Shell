#!/usr/bin/env python
"""
AI Shell Assistant - Main Entry Point

This is a Python script that uses AI APIs to interact with a Linux terminal.
It is designed to be an agentic AI assistant that can execute commands and provide
explanations based on the user's input.

The application features:
- Natural language command execution
- Multiple AI model support
- Conversation management
- Incognito mode for privacy
- Web search capabilities
- Enhanced security features

Usage:
    python main.py

Configuration:
    - config.yaml: Main configuration file
    - context.md: Additional context and user preferences

This script is split into several modules for better organization:
- app.py: Main application logic
- chat.py: AI chat management
- commands.py: Command execution
- config.py: Configuration handling
- ui.py: User interface
- models.py: Model management
- conversation_manager.py: Conversation persistence
- terminal_input.py: Enhanced terminal input
- web_search.py: Web search functionality
- logger.py: Logging system
- constants.py: Application constants
"""

import sys
import os

# Add parent directory to path for direct execution
if __name__ == "__main__":
    # Get the directory containing this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Add the parent of ai_shell to sys.path (the src directory)
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

from ai_shell.app import AIShellApp


def main() -> None:
    """Main entry point for the AI Shell Assistant"""
    app = AIShellApp()
    
    try:
        app.initialize()
        app.run()
    except Exception as e:
        app.ui.show_error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
