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

def execute_command(command):
    """Execute an interactive command using pty for real terminal interaction with directory persistence"""
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
        
        # Get the current working directory from our cache
        start_cwd = get_current_directory()
        
        # Prepare the command to run in the correct directory
        # We need to ensure the command starts from the current cached directory
        wrapped_command = f"cd '{start_cwd}' && {command}"
        
        process = subprocess.Popen(
            ['/bin/bash', '-c', wrapped_command],
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
            
            # Clean up the master fd
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
        
        # After the interactive command completes, detect the final working directory
        # We'll run a separate command to get the final directory after the command execution
        try:
            # Create a new pty session to get the final directory
            detect_master_fd, detect_slave_fd = pty.openpty()
            
            # Run the same command sequence but with pwd at the end to detect final directory
            detect_command = f"cd '{start_cwd}' && {command} >/dev/null 2>&1; pwd"
            
            detect_process = subprocess.Popen(
                ['/bin/bash', '-c', detect_command],
                stdin=detect_slave_fd,
                stdout=detect_slave_fd,
                stderr=detect_slave_fd,
                env=env,
                preexec_fn=os.setsid
            )
            
            os.close(detect_slave_fd)
            
            # Read the output to get the final directory
            final_dir_output = ""
            try:
                while detect_process.poll() is None:
                    ready, _, _ = select.select([detect_master_fd], [], [], 0.1)
                    if ready:
                        data = os.read(detect_master_fd, 1024)
                        if data:
                            final_dir_output += data.decode('utf-8', errors='replace')
                
                # Read any remaining output
                while True:
                    ready, _, _ = select.select([detect_master_fd], [], [], 0.1)
                    if not ready:
                        break
                    data = os.read(detect_master_fd, 1024)
                    if not data:
                        break
                    final_dir_output += data.decode('utf-8', errors='replace')
                    
            except OSError:
                pass
            finally:
                os.close(detect_master_fd)
                if detect_process.poll() is None:
                    try:
                        os.killpg(os.getpgid(detect_process.pid), signal.SIGTERM)
                        detect_process.wait(timeout=2)
                    except:
                        try:
                            os.killpg(os.getpgid(detect_process.pid), signal.SIGKILL)
                        except:
                            pass
            
            # Extract the final directory from the output
            final_dir_lines = final_dir_output.strip().split('\n')
            if final_dir_lines:
                final_dir = final_dir_lines[-1].strip()
                if final_dir and os.path.exists(final_dir) and final_dir != get_current_directory():
                    # Directory changed, update our cache and sync the persistent shell
                    sync_directory_to_shell(final_dir)
                    
        except Exception:
            # If we can't detect the directory change, fall back to updating from persistent shell
            try:
                update_cached_directory()
            except:
                pass
        
        output = ''.join(output_lines)
        success = exit_code == 0
        return success, output
        
    except Exception as e:
        console = Console()
        console.print(f"[red]Error executing interactive command: {e}[/red]")
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

def sync_directory_to_shell(new_directory):
    """Sync both the cached directory and the persistent shell to a new directory"""
    global _cached_directory
    try:
        # Update the cached directory
        if os.path.exists(new_directory):
            _cached_directory = new_directory
            
            # Sync the persistent shell to this directory
            shell = get_shell()
            if shell.stdin:
                shell.stdin.write(f"cd '{new_directory}'\n")
                shell.stdin.flush()
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
