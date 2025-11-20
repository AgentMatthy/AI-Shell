#!/usr/bin/env python

import os
import subprocess
import pty
import select
import sys
import signal
import termios
import tty
import shlex
from rich.console import Console
from typing import Tuple

try:
    from .logger import logger
    from .constants import DANGEROUS_COMMAND_PATTERNS, DIR_CHANGING_COMMANDS, COMMAND_TIMEOUT
except ImportError:
    # Fallback for when running as standalone
    logger = None
    DANGEROUS_COMMAND_PATTERNS = []
    DIR_CHANGING_COMMANDS = ['cd', 'pushd', 'popd']
    COMMAND_TIMEOUT = 5

def validate_command(command: str) -> Tuple[bool, str]:
    """Validate command for basic checks"""
    if not command or not command.strip():
        return False, "Empty command"
    
    # Remove excessive whitespace
    command = command.strip()
    
    # Log command validation
    if logger:
        logger.debug(f"Command validated: {command}")
    return True, ""


def execute_command(command: str) -> Tuple[bool, str]:
    """Execute an interactive command using pty for real terminal interaction with directory persistence"""
    
    # Validate command first
    is_valid, validation_error = validate_command(command)
    if not is_valid:
        console = Console()
        console.print(f"[red]Command validation failed: {validation_error}[/red]")
        return False, f"Command validation failed: {validation_error}"
    
    try:
        # Save current terminal settings
        old_settings = None
        master_fd = None
        process = None
        
        try:
            if sys.stdin.isatty():
                old_settings = termios.tcgetattr(sys.stdin.fileno())
        except (OSError, termios.error) as e:
            console = Console()
            console.print(f"[yellow]Warning: Could not save terminal settings: {e}[/yellow]")
        
        # Create a pseudo-terminal
        try:
            master_fd, slave_fd = pty.openpty()
        except OSError as e:
            console = Console()
            console.print(f"[red]Error creating pseudo-terminal: {e}[/red]")
            return False, f"Error creating pseudo-terminal: {e}"
        
        # Start the process with the slave end of the pty
        env = dict(os.environ)
        env['TERM'] = 'xterm-256color'  # Enable colors
        env['FORCE_COLOR'] = '1'
        env['COLORTERM'] = 'truecolor'
        
        # Get the current working directory from our cache
        start_cwd = get_current_directory()
        
        # Validate the directory exists
        if not os.path.exists(start_cwd) or not os.path.isdir(start_cwd):
            console = Console()
            console.print(f"[yellow]Warning: Cached directory {start_cwd} doesn't exist, using current working directory[/yellow]")
            start_cwd = os.getcwd()
            _set_current_directory(start_cwd)
        
        # Prepare the command to run in the correct directory
        # We need to ensure the command starts from the current cached directory
        wrapped_command = f"cd '{start_cwd}' && {command}"
        
        try:
            process = subprocess.Popen(
                ['/bin/bash', '-c', wrapped_command],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                preexec_fn=os.setsid
            )
        except (OSError, subprocess.SubprocessError) as e:
            console = Console()
            console.print(f"[red]Error starting process: {e}[/red]")
            os.close(slave_fd)
            os.close(master_fd)
            return False, f"Error starting process: {e}"
        
        # Close the slave end in the parent process
        os.close(slave_fd)
        
        # Set terminal to raw mode if we're in a tty
        try:
            if sys.stdin.isatty():
                tty.setraw(sys.stdin.fileno())
        except (OSError, termios.error) as e:
            console = Console()
            console.print(f"[yellow]Warning: Could not set terminal to raw mode: {e}[/yellow]")
        
        # Handle I/O between terminal and subprocess
        output_lines = []
        
        try:
            while process.poll() is None:
                ready, _, _ = select.select([sys.stdin, master_fd], [], [], 0.1)
                
                if sys.stdin in ready:
                    # Read from stdin and write to master
                    try:
                        data = os.read(sys.stdin.fileno(), 1024)
                        if data:
                            os.write(master_fd, data)
                    except OSError:
                        break
                
                if master_fd in ready:
                    # Read from master and write to stdout
                    try:
                        data = os.read(master_fd, 1024)
                        if data:
                            decoded_data = data.decode('utf-8', errors='replace')
                            sys.stdout.write(decoded_data)
                            sys.stdout.flush()
                            output_lines.append(decoded_data)
                    except OSError:
                        break
            
            # Wait for process to complete
            exit_code = process.wait()
            
            # Read any remaining output
            try:
                while True:
                    ready, _, _ = select.select([master_fd], [], [], 0.1)
                    if not ready:
                        break
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    decoded_data = data.decode('utf-8', errors='replace')
                    sys.stdout.write(decoded_data)
                    sys.stdout.flush()
                    output_lines.append(decoded_data)
            except OSError:
                pass
            
        finally:
            # Restore terminal settings
            try:
                if old_settings and sys.stdin.isatty():
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
            except (OSError, termios.error) as e:
                # Don't break execution for terminal restoration issues
                pass
            
            # Clean up the master fd
            try:
                if master_fd is not None:
                    os.close(master_fd)
            except OSError:
                pass
                
            # Clean up process
            if process and process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired, ProcessLookupError):
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        pass
        
        # Detect directory changes after command execution
        # This works for any command that might change the directory
        if not command.strip().startswith('sudo'):
            try:
                # Check if this command could potentially change the directory
                command_words = command.strip().split()
                might_change_dir = any(cmd_word in DIR_CHANGING_COMMANDS for cmd_word in command_words)
                
                if might_change_dir:
                    # Execute the command in a new shell session to detect the final directory
                    # This approach works for all variants: cd, cd ~, cd .., cd /path, etc.
                    try:
                        final_dir_result = subprocess.run(
                            ['/bin/bash', '-c', f"cd '{start_cwd}' && {command} 2>/dev/null && pwd"],
                            capture_output=True,
                            text=True,
                            timeout=COMMAND_TIMEOUT,
                            cwd=start_cwd
                        )
                        
                        if final_dir_result.returncode == 0:
                            final_dir = final_dir_result.stdout.strip()
                            if final_dir and os.path.exists(final_dir) and final_dir != get_current_directory():
                                # Directory changed, update our cache
                                _set_current_directory(final_dir)
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
                        # If we can't detect the directory change, that's ok
                        pass
                        
            except Exception:
                # If we can't detect the directory change, that's ok
                pass
        
        output = ''.join(output_lines)
        success = exit_code == 0
        
        # Log command execution
        if logger:
            logger.log_command_execution(command, success, output[:200] if output else "")
        
        return success, output
        
    except Exception as e:
        console = Console()
        console.print(f"[red]Error executing interactive command: {e}[/red]")
        return False, str(e)


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
