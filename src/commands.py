#!/usr/bin/env python

import os
import subprocess
from rich.console import Console

def execute_command(command):
    """Execute a command and capture output while maintaining directory state"""
    try:
        # Get current working directory
        current_dir = get_current_directory()
        
        # Create environment with color support
        env = dict(os.environ)
        env.update({
            'TERM': 'xterm-256color',
            'FORCE_COLOR': '1',
            'COLORTERM': 'truecolor'
        })
        
        # Execute command in current directory
        process = subprocess.Popen(
            ['/bin/bash', '-c', command],
            cwd=current_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )
        
        # Read output line by line for real-time display
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                # Display output in real-time
                print(line, end='')
                output_lines.append(line)
        
        # Wait for process to complete
        exit_code = process.wait()
        
        # Update directory if command might have changed it
        _update_directory_after_command(command, current_dir)
        
        output = ''.join(output_lines)
        success = exit_code == 0
        return success, output
        
    except Exception as e:
        console = Console()
        console.print(f"[red]Error executing command: {e}[/red]")
        return False, str(e)

def _update_directory_after_command(command, original_dir):
    """Update cached directory if command might have changed it"""
    # Check if command might change directory
    cd_commands = ['cd', 'pushd', 'popd']
    if any(cmd in command.split() for cmd in cd_commands):
        try:
            # Get the new directory by running pwd
            result = subprocess.run(
                ['/bin/bash', '-c', f"cd '{original_dir}' && {command} >/dev/null 2>&1 && pwd"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                new_dir = result.stdout.strip()
                if new_dir and os.path.exists(new_dir) and new_dir != original_dir:
                    _set_current_directory(new_dir)
        except (subprocess.TimeoutExpired, Exception):
            # If we can't detect directory change, keep original
            pass

def _set_current_directory(new_dir):
    """Set the cached current directory"""
    global _cached_directory
    _cached_directory = new_dir

# Cache for current directory
_cached_directory = os.getcwd()

def get_current_directory():
    """Get current directory (cached)"""
    return _cached_directory

def get_prompt_directory():
    """Get a formatted directory for the prompt (shortened if needed)"""
    current_dir = get_current_directory()
    home_dir = os.path.expanduser("~")
    
    # Replace home directory with ~
    if current_dir.startswith(home_dir):
        display_dir = "~" + current_dir[len(home_dir):]
    else:
        display_dir = current_dir
    
    # Shorten very long paths
    if len(display_dir) > 40:
        parts = display_dir.split(os.sep)
        if len(parts) > 3:
            display_dir = os.sep.join([parts[0], "...", parts[-2], parts[-1]])
    
    return display_dir
