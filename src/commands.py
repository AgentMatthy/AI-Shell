#!/usr/bin/env python

import os
import subprocess
import atexit
import pty
import select
import sys
import signal
import termios
import tty
import shlex
import re
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
            bufsize=1,
            env=dict(os.environ, TERM='xterm-256color')  # Enable colors
        )
    return _persistent_shell

def cleanup_shell():
    """Clean up the persistent shell process"""
    global _persistent_shell
    if _persistent_shell:
        try:
            if _persistent_shell.stdin:
                _persistent_shell.stdin.write('exit\n')
                _persistent_shell.stdin.flush()
            _persistent_shell.wait(timeout=2)
        except:
            _persistent_shell.kill()
        _persistent_shell = None

def is_interactive_command(command):
    """Check if a command is likely to be interactive"""
    interactive_commands = [
        'yay', 'pacman', 'apt', 'sudo', 'passwd', 'su', 'ssh', 'scp', 'ftp', 'sftp',
        'mysql', 'psql', 'sqlite3', 'mongo', 'redis-cli', 'docker', 'kubectl',
        'vim', 'nano', 'emacs', 'less', 'more', 'man', 'htop', 'top', 'watch',
        'python', 'python3', 'node', 'npm', 'yarn', 'git', 'make', 'cmake'
    ]
    
    # Check if command starts with any interactive command
    cmd_parts = command.strip().split()
    if cmd_parts:
        base_cmd = cmd_parts[0]
        return any(base_cmd.startswith(ic) or base_cmd.endswith(ic) for ic in interactive_commands)
    
    return False

def execute_command_interactive(command):
    """Execute an interactive command using pty for real terminal interaction"""
    try:
        # Save current terminal settings
        old_settings = None
        if sys.stdin.isatty():
            old_settings = termios.tcgetattr(sys.stdin.fileno())
        
        # Create a pseudo-terminal
        master_fd, slave_fd = pty.openpty()
        
        # Start the process with the slave end of the pty
        env = dict(os.environ)
        env['TERM'] = 'xterm-256color'  # Enable colors
        env['FORCE_COLOR'] = '1'
        env['COLORTERM'] = 'truecolor'
        
        process = subprocess.Popen(
            command,
            shell=True,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            preexec_fn=os.setsid
        )
        
        # Close the slave end in the parent process
        os.close(slave_fd)
        
        # Set terminal to raw mode if we're in a tty
        if sys.stdin.isatty():
            tty.setraw(sys.stdin.fileno())
        
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
            if old_settings and sys.stdin.isatty():
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
            
            # Clean up
            os.close(master_fd)
            if process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=2)
                except:
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except:
                        pass
        
        output = ''.join(output_lines)
        success = exit_code == 0
        return success, output
        
    except Exception as e:
        console = Console()
        console.print(f"[red]Error executing interactive command: {e}[/red]")
        return False, str(e)

def execute_command(command):
    """Execute a command with appropriate method based on interactivity"""
    console = Console()
    
    # # Check if this is likely an interactive command
    # if is_interactive_command(command):
    #     return execute_command_interactive(command)

    return execute_command_interactive(command)
    
    # Use existing method for non-interactive commands with color support
    try:
        shell = get_shell()
        
        # Send command with a unique end marker, forcing color output
        end_marker = f"__END__{os.getpid()}__"
        full_command = f"FORCE_COLOR=1 COLORTERM=truecolor {command}; echo '{end_marker}'\n"
        
        if shell.stdin:
            shell.stdin.write(full_command)
            shell.stdin.flush()
        else:
            raise RuntimeError("Shell stdin is not available")
        
        # Read output until we see the end marker
        output_lines = []
        if not shell.stdout:
            raise RuntimeError("Shell stdout is not available")
            
        while True:
            line = shell.stdout.readline()
            if not line:
                break
            
            if end_marker in line:
                break
                
            # Print with color support - don't strip ANSI codes
            print(line, end='', flush=True)
            output_lines.append(line)
        
        # Get exit code
        if shell.stdin:
            shell.stdin.write(f"echo $?; echo '{end_marker}'\n")
            shell.stdin.flush()
        else:
            raise RuntimeError("Shell stdin is not available")
        
        exit_code = 0
        while True:
            if not shell.stdout:
                break
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
        
        if not shell.stdin or not shell.stdout:
            return
            
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
