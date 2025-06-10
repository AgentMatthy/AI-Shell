#!/usr/bin/env python

import os
import subprocess
import atexit
from rich.console import Console

# Global persistent shell process for command execution
_persistent_shell = None

def get_shell():
    """Get or create the global persistent shell process"""
    global _persistent_shell
    if _persistent_shell is None or _persistent_shell.poll() is not None:
        _persistent_shell = subprocess.Popen(
            ['/bin/bash'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
    return _persistent_shell

def cleanup_shell():
    """Clean up the persistent shell process"""
    global _persistent_shell
    if _persistent_shell:
        try:
            _persistent_shell.stdin.write('exit\n')
            _persistent_shell.stdin.flush()
            _persistent_shell.wait(timeout=2)
        except:
            _persistent_shell.kill()
        _persistent_shell = None

def execute_command(command):
    """Execute a command in the persistent shell"""
    console = Console()
    
    try:
        shell = get_shell()
        
        # Send command with a unique end marker
        end_marker = f"__END__{os.getpid()}__"
        full_command = f"{command}; echo '{end_marker}'\n"
        
        shell.stdin.write(full_command)
        shell.stdin.flush()
        
        # Read output until we see the end marker
        output_lines = []
        while True:
            line = shell.stdout.readline()
            if not line:
                break
            
            if end_marker in line:
                break
                
            print(line, end='', flush=True)
            output_lines.append(line)
        
        # Get exit code
        shell.stdin.write(f"echo $?; echo '{end_marker}'\n")
        shell.stdin.flush()
        
        exit_code = 0
        while True:
            line = shell.stdout.readline()
            if not line:
                break
            
            if end_marker in line:
                break
                
            line = line.strip()
            if line.isdigit():
                exit_code = int(line)
        
        # Update cached directory if command might have changed it
        # if any(cmd in command.lower() for cmd in ['cd ', 'pushd ', 'popd']):
        update_cached_directory()
        
        output = ''.join(output_lines)
        success = exit_code == 0
        return success, output
        
    except Exception as e:
        console.print(f"[red]Error executing command: {e}[/red]")
        return False, str(e)

# Cache for current directory
_cached_directory = os.getcwd()

def update_cached_directory():
    """Update the cached directory from the shell"""
    global _cached_directory
    try:
        shell = get_shell()
        end_marker = f"__PWD__{os.getpid()}__"
        
        shell.stdin.write(f"pwd; echo '{end_marker}'\n")
        shell.stdin.flush()
        
        while True:
            line = shell.stdout.readline()
            if not line:
                break
                
            if end_marker in line:
                break
                
            line = line.strip()
            if line and os.path.exists(line):
                _cached_directory = line
                # Don't print this line - just consume it silently
                
    except:
        pass

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

# Register cleanup
atexit.register(cleanup_shell)
