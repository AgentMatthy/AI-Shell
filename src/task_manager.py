#!/usr/bin/env python

from .commands import execute_command
from .ui import UIManager

class TaskManager:
    def __init__(self, chat_manager, ui_manager=None):
        self.chat_manager = chat_manager
        self.ui_manager = ui_manager or UIManager()
    
    def execute_task(self, user_input, ai_response):
        """Execute a task based on AI response and check completion"""
        # Extract command from AI response (look for code blocks or command indicators)
        command = self._extract_command_from_response(ai_response)
        
        if not command:
            self.ui_manager.show_warning("No executable command found in AI response")
            return False
        
        # Show the command that will be executed
        self.ui_manager.show_command_execution(command)
        
        # Execute the command
        return_code, output = execute_command(command)
        
        # Check task completion status
        completed, reason = self.chat_manager.check_task_status(output, user_input)
        
        if completed is not None:
            self.ui_manager.show_task_status(completed, reason)
        
        return return_code == 0
    
    def _extract_command_from_response(self, response):
        """Extract executable command from AI response"""
        lines = response.split('\n')
        
        # Look for code blocks
        in_code_block = False
        command_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Check for code block markers
            if line.startswith('```') and ('bash' in line or 'sh' in line or line == '```'):
                in_code_block = True
                continue
            elif line == '```' and in_code_block:
                in_code_block = False
                break
            elif in_code_block and line:
                # Skip comments in code blocks
                if not line.startswith('#'):
                    command_lines.append(line)
            
            # Also look for lines that start with $ (shell prompt indicator)
            elif line.startswith('$ '):
                command_lines.append(line[2:])  # Remove '$ ' prefix
        
        # If we found commands in code blocks, use those
        if command_lines:
            return ' && '.join(command_lines)
        
        # Fallback: look for common command patterns in the response
        command_indicators = [
            'run:', 'execute:', 'command:', 'type:', 'use:'
        ]
        
        for line in lines:
            line = line.strip()
            for indicator in command_indicators:
                if line.lower().startswith(indicator):
                    potential_command = line[len(indicator):].strip()
                    if potential_command:
                        return potential_command
        
        return None
