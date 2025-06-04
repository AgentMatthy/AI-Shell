#!/usr/bin/env python

import os
import pty
import subprocess
import threading
import select
import sys
from rich.console import Console

def decode_output(output, fallback_encoding='latin-1'):
    """Safely decode output with fallback encoding"""
    try:
        return output.decode('utf-8')
    except UnicodeDecodeError:
        try:
            return output.decode(fallback_encoding)
        except UnicodeDecodeError:
            return output.decode('utf-8', errors='replace')

def execute_command(command):
    """Execute a command in a PTY and capture output in real-time"""
    console = Console()
    
    master_fd, slave_fd = pty.openpty()
    
    try:
        # Start the process
        process = subprocess.Popen(
            command,
            shell=True,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
            close_fds=True
        )
        
        os.close(slave_fd)
        
        # Set non-blocking mode for the master fd
        import fcntl
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        output_buffer = b""
        
        def handle_user_input():
            """Handle user input in a separate thread"""
            while process.poll() is None:
                try:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        user_input = sys.stdin.read(1)
                        if user_input:
                            os.write(master_fd, user_input.encode())
                except (OSError, IOError):
                    break
        
        input_thread = threading.Thread(target=handle_user_input, daemon=True)
        input_thread.start()
        
        while process.poll() is None:
            try:
                ready, _, _ = select.select([master_fd], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(master_fd, 8192)
                        if chunk:
                            output_buffer += chunk
                            # Print output in real-time
                            decoded_chunk = decode_output(chunk)
                            print(decoded_chunk, end='', flush=True)
                    except OSError:
                        break
            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully
                try:
                    os.killpg(os.getpgid(process.pid), 2)  # Send SIGINT
                except OSError:
                    pass
                break
        
        # Capture any remaining output
        try:
            while True:
                ready, _, _ = select.select([master_fd], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(master_fd, 8192)
                        if chunk:
                            output_buffer += chunk
                            decoded_chunk = decode_output(chunk)
                            print(decoded_chunk, end='', flush=True)
                        else:
                            break
                    except OSError:
                        break
                else:
                    break
        except KeyboardInterrupt:
            pass
        
        return_code = process.wait()
        
    except Exception as e:
        console.print(f"[red]Error executing command: {e}[/red]")
        return_code = 1
        output_buffer = b""
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
    
    decoded_output = decode_output(output_buffer)
    # Return success (True/False) and output
    success = return_code == 0
    return success, decoded_output
