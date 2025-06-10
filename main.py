#!/usr/bin/env python

# This is a Python script that uses the OpenAI API to interact with a Linux terminal.
# It is designed to be an agentic ai assistant that can execute commands and provide
# explanations based on the user's input.

# This script is split into several other files for better organization. Add new code to the relevant files.

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.app import AIShellApp

def main():
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
