#!/usr/bin/env python

# This is a Python script that uses the OpenAI API to interact with a Linux terminal.
# It is designed to be an agentic ai assistant that can execute commands and provide
# explanations based on the user's input.

import re, json
import subprocess
import os
import sys

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install it with: pip install PyYAML")
    sys.exit(1)

from openai import OpenAI
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown

def load_config(config_path="config.yaml"):
    """Load configuration from YAML file"""
    if not os.path.exists(config_path):
        console.print(f"[red]Error: Config file '{config_path}' not found![/red]")
        console.print(f"[yellow]Please create a config.yaml file with your API settings.[/yellow]")
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Handle both old and new config formats
        if "models" in config:
            # Check for new dual-model format
            if "response_model" in config["models"] and "task_checker_model" in config["models"]:
                # New dual-model format
                required_fields = ["api.url", "api.api_key", "models.response_model", "models.task_checker_model"]
                for field in required_fields:
                    keys = field.split('.')
                    value = config
                    for key in keys:
                        if key not in value:
                            console.print(f"[red]Error: Missing required config field: {field}[/red]")
                            sys.exit(1)
                        value = value[key]
                    
                    if not value or value == "your_api_key_here":
                        console.print(f"[red]Error: Please set a valid value for {field}[/red]")
                        sys.exit(1)
            elif "default" in config["models"]:
                # Legacy multi-model format - convert to dual-model format
                required_fields = ["api.url", "api.api_key", "models.default"]
                for field in required_fields:
                    keys = field.split('.')
                    value = config
                    for key in keys:
                        if key not in value:
                            console.print(f"[red]Error: Missing required config field: {field}[/red]")
                            sys.exit(1)
                        value = value[key]
                    
                    if not value or value == "your_api_key_here":
                        console.print(f"[red]Error: Please set a valid value for {field}[/red]")
                        sys.exit(1)
                
                # Convert to dual-model format internally
                default_model = config["models"]["default"]
                config["models"]["response_model"] = default_model
                config["models"]["task_checker_model"] = default_model
            else:
                console.print(f"[red]Error: Invalid models configuration format[/red]")
                sys.exit(1)
        else:
            # Legacy single model format - convert to dual-model format
            required_fields = ["api.url", "api.api_key", "api.model"]
            for field in required_fields:
                keys = field.split('.')
                value = config
                for key in keys:
                    if key not in value:
                        console.print(f"[red]Error: Missing required config field: {field}[/red]")
                        sys.exit(1)
                    value = value[key]
                
                if not value or value == "your_api_key_here":
                    console.print(f"[red]Error: Please set a valid value for {field}[/red]")
                    sys.exit(1)
            
            # Convert to new format internally
            model_name = config["api"]["model"]
            config["models"] = {
                "response_model": "default",
                "task_checker_model": "default",
                "available": {
                    "default": {
                        "name": model_name,
                        "alias": "default",
                        "display_name": model_name.split('/')[-1]
                    }
                }
            }
        
        return config
    except yaml.YAMLError as e:
        console.print(f"[red]Error: Invalid YAML in config file: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)

# Initialize Rich console first (needed for config loading error messages)
console = Console()

# Load configuration
CONFIG = load_config()
API_CONFIG = CONFIG["api"]
SETTINGS = CONFIG.get("settings", {})

# Initialize model management
MODELS = CONFIG["models"]
current_response_model = MODELS["response_model"]
current_task_checker_model = MODELS["task_checker_model"]

# System prompt
SYSTEM_PROMPT = """
You are a Linux terminal assistant Agent. You can provide explanations and execute commands naturally.

COMMAND FORMAT: When you need to run a command, use command blocks like this:

```command
ls -la /home
```

You can include explanations before and after command blocks naturally:

Example response:
"Let me check what's in your home directory:

```command
ls -la /home
```

This will show all files including hidden ones."

RULES:
1. Use ```command blocks ONLY for commands you want executed
2. You can mix explanations and commands naturally in the same response
3. Each command block should contain exactly one command
4. CRITICAL: Use ONLY ONE command block per response - NEVER multiple commands
5. Always explain what the command will do
6. After each command, wait to see the result before proceeding with additional commands
7. Execute commands one at a time and analyze results before continuing

COMMAND EXECUTION STRATEGY:
- Execute EXACTLY ONE command per response
- Wait for the result before deciding on the next step
- Analyze command output before proceeding
- Never assume commands will succeed - always check results first

INFORMATION GATHERING:
- NEVER assume system details - discover them with commands
- When uncertain about system info that commands can reveal, USE COMMANDS:
  * OS: 'uname -a', 'cat /etc/os-release', 'lsb_release -a'
  * Software: 'which', 'command -v', 'dpkg -l', 'rpm -qa', 'pacman -Q'
  * Config: 'cat', 'grep', 'find' for config files
  * Hardware: 'lscpu', 'free -h', 'df -h', 'lsblk'
  * Network: 'ip addr', 'netstat', 'ss'
  * Processes: 'ps', 'top', 'systemctl'
- When multiple approaches exist and choice matters, ASK THE USER
- Examples: "Do you want to install via apt, snap, or compile from source?"

The host OS is Linux - use appropriate Linux commands only.
"""

# Initialize Rich components
console = Console()

# Initialize OpenAI client
client = OpenAI(api_key=API_CONFIG["api_key"], base_url=API_CONFIG["url"])

payload = [{"role": "system", "content": SYSTEM_PROMPT}]

def get_model_display_name(model_alias):
    """Get the model's display name by alias"""
    if model_alias in MODELS["available"]:
        return MODELS["available"][model_alias]["display_name"]
    return model_alias

def get_model_api_name(model_alias):
    """Get the model's API name by alias"""
    if model_alias in MODELS["available"]:
        return MODELS["available"][model_alias]["name"]
    return model_alias

def get_current_response_model_name():
    """Get the current response model's display name"""
    return get_model_display_name(current_response_model)

def get_current_response_model_api_name():
    """Get the current response model's API name"""
    return get_model_api_name(current_response_model)

def get_current_task_checker_model_api_name():
    """Get the current task checker model's API name"""
    return get_model_api_name(current_task_checker_model)

def list_models():
    """Display available models and current configuration"""
    console.print("\n[bold cyan]Current Model Configuration:[/bold cyan]")
    response_display = get_model_display_name(current_response_model)
    task_checker_display = get_model_display_name(current_task_checker_model)
    console.print(f"  Response Model: [yellow]{current_response_model}[/yellow] - {response_display}")
    console.print(f"  Task Checker Model: [yellow]{current_task_checker_model}[/yellow] - {task_checker_display}")
    
    console.print("\n[bold cyan]Available models:[/bold cyan]")
    for alias, model_info in MODELS["available"].items():
        response_marker = "[R]" if alias == current_response_model else "[ ]"
        task_marker = "[T]" if alias == current_task_checker_model else "[ ]"
        display_name = model_info["display_name"]
        console.print(f"  {response_marker}{task_marker} [yellow]{alias}[/yellow] - {display_name}")
    console.print("\n[dim]Legend: [R] = Response Model, [T] = Task Checker Model[/dim]")
    console.print()

def switch_model(model_spec):
    """Switch models. Format: 'alias' (both models) or 'response_alias:task_alias'"""
    global current_response_model, current_task_checker_model
    
    if ':' in model_spec:
        # Format: response_model:task_checker_model
        response_alias, task_alias = model_spec.split(':', 1)
        
        if response_alias not in MODELS["available"]:
            console.print(f"[red]Error: Response model '{response_alias}' not found.[/red]")
            console.print("[yellow]Use /models to see available models.[/yellow]")
            return False
            
        if task_alias not in MODELS["available"]:
            console.print(f"[red]Error: Task checker model '{task_alias}' not found.[/red]")
            console.print("[yellow]Use /models to see available models.[/yellow]")
            return False
        
        current_response_model = response_alias
        current_task_checker_model = task_alias
        
        response_info = MODELS["available"][current_response_model]
        task_info = MODELS["available"][current_task_checker_model]
        console.print(f"[green]✓ Response: {response_info['display_name']}[/green]")
        console.print(f"[green]✓ Task checker: {task_info['display_name']}[/green]")
    else:
        # Single model - use for both response and task checking
        if model_spec not in MODELS["available"]:
            console.print(f"[red]Error: Model '{model_spec}' not found.[/red]")
            console.print("[yellow]Use /models to see available models.[/yellow]")
            return False
        
        current_response_model = model_spec
        current_task_checker_model = model_spec
        model_info = MODELS["available"][model_spec]
        console.print(f"[green]Both models switched to: {model_info['display_name']}[/green]")
    
    return True

def check_task_status(model_client, original_request, conversation_context) -> str:
    """
    Check if the overall task is complete or if more steps are needed.
    Returns: [COMPLETE], [CONTINUE], or [FAILED]
    """
    prompt = f"""
You are a task completion analyzer. Your job is to determine if a user's original request has been fully completed based on the conversation history.

Original user request: {original_request}

Recent conversation context: {conversation_context}

Analyze whether:
1. The original request has been FULLY completed (all parts addressed)
2. More steps are needed to complete the request (CONTINUE with next step)
3. The task has failed and cannot be completed (FAILED)

Respond with ONLY one of these formats:
- "[COMPLETE]" - if the original request is fully satisfied
- "[CONTINUE]" - if more steps are needed to complete the original request
- "[FAILED]" - if the task cannot be completed

It is VERY important to only use one of these responses, as if you reply with anything else, it will break the parsing.
Do not give reasons for the response, just answer with [COMPLETE], [CONTINUE], or [FAILED].

IMPORTANT GUIDELINES:
- Be VERY conservative about marking tasks as FAILED
- Only use FAILED if the task is fundamentally impossible (e.g., accessing non-existent files, invalid operations)
- Command errors, permission issues, or temporary failures should result in [CONTINUE], not [FAILED]
- If a command failed but alternative approaches exist, use [CONTINUE]
- Failed commands are learning opportunities - the AI can try different approaches
- Most tasks that encounter errors can be solved with different commands or approaches
    """
    
    with console.status("[bold bright_black]Checking...[/bold bright_black]", spinner_style="bright_black"):
        response = model_client.chat.completions.create(
            model=get_current_task_checker_model_api_name(),
            messages=[{"role": "system", "content": prompt}]
        )
    
    return response.choices[0].message.content.strip()

def check_if_question(model_client, ai_response) -> bool:
    """
    Check if the AI's response is asking a question that requires user input.
    Returns: True if it's a question requiring user input, False otherwise
    """
    prompt = f"""
You are analyzing an AI assistant's response to determine if it contains a question that requires user input.

AI Response: {ai_response}

Determine if this response contains a question that requires the user to provide input, make a choice, or clarify something.

Examples of responses that ARE questions requiring user input:
- "Which directory would you like to search?"
- "Do you want to install via apt or snap?"
- "What filename should I use?"
- "Please specify the target directory"

Examples of responses that are NOT questions requiring user input:
- "Here's the information you requested"
- "The command completed successfully"
- "I found 3 files in the directory"
- "The installation is complete"

Respond with ONLY:
- "[QUESTION]" - if the response requires user input
- "[NO_QUESTION]" - if the response does not require user input

It is VERY important to only use one of these responses, as if you reply with anything else, it will break the parsing.
    """
    
    with console.status("[bold bright_black]Analyzing...[/bold bright_black]", spinner_style="bright_black"):
        response = model_client.chat.completions.create(
            model=get_current_task_checker_model_api_name(),
            messages=[{"role": "system", "content": prompt}]
        )
    
    result = response.choices[0].message.content.strip()
    return "[QUESTION]" in result

def get_chat_response(client: OpenAI, payload: list) -> tuple[str, str]:
    """Get chat response"""
    response = client.chat.completions.create(
        model=get_current_response_model_api_name(), messages=payload, stream=True
    )
    reply_chunk, reasoning_chunk = [], []
    full_reply = ""
    has_reasoning = False
    with console.status("[bold green]Thinking...[/bold green]") as status:
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                reply_chunk.append(content)
                full_reply += content
            
            if hasattr(chunk.choices[0].delta, 'reasoning_content'):
                reasoning_content = getattr(chunk.choices[0].delta, 'reasoning_content', None)
                if reasoning_content:
                    has_reasoning = True
                    reasoning_chunk.append(reasoning_content)
                    status.stop()
                    console.print(reasoning_content, end="")
                
    if has_reasoning:
        print()
        
    return "".join(reply_chunk), "".join(reasoning_chunk)

def decode_output(output_bytes: bytes) -> str:
    """Try to decode byte string using common encodings."""
    encodings = ['utf-8', 'gbk', 'cp936']  # Common encodings, especially for Windows
    for enc in encodings:
        try:
            return output_bytes.decode(enc)
        except UnicodeDecodeError:
            #print(f"Decoding with {enc} failed, trying next encoding...")
            continue
    # Default to UTF-8 with error replacement
    return output_bytes.decode('utf-8', errors='replace')

def execute_command(command: str) -> tuple[bool, str]:
    """Execute the command with full interactive real-time I/O."""
    import select
    import sys
    import tty
    import termios
    
    try:
        # Start the process with PTY for true interactive behavior
        import pty
        master_fd, slave_fd = pty.openpty()
        
        process = subprocess.Popen(
            command,
            shell=True,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid
        )
        
        # Close slave fd in parent process
        os.close(slave_fd)
        
        # Store terminal settings
        old_settings = None
        try:
            old_settings = termios.tcgetattr(sys.stdin.fileno())
            tty.setraw(sys.stdin.fileno())
        except:
            pass  # Might fail in some environments
        
        output_buffer = []
        
        try:
            while True:
                # Check if process is still running
                if process.poll() is not None:
                    break
                
                # Use select to check for available input/output
                ready, _, _ = select.select([sys.stdin, master_fd], [], [], 0.1)
                
                # Handle user input
                if sys.stdin in ready:
                    try:
                        user_input = os.read(sys.stdin.fileno(), 1024)
                        if user_input:
                            os.write(master_fd, user_input)
                    except OSError:
                        break
                
                # Handle command output
                if master_fd in ready:
                    try:
                        output = os.read(master_fd, 1024)
                        if output:
                            decoded_output = output.decode('utf-8', errors='replace')
                            print(decoded_output, end='', flush=True)
                            output_buffer.append(decoded_output)
                        else:
                            break
                    except OSError:
                        break
            
            # Get any remaining output
            try:
                while True:
                    ready, _, _ = select.select([master_fd], [], [], 0.1)
                    if not ready:
                        break
                    output = os.read(master_fd, 1024)
                    if not output:
                        break
                    decoded_output = output.decode('utf-8', errors='replace')
                    print(decoded_output, end='', flush=True)
                    output_buffer.append(decoded_output)
            except OSError:
                pass
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted[/yellow]")
            try:
                os.killpg(os.getpgid(process.pid), 2)  # Send SIGINT to process group
            except:
                process.terminate()
            return False, "Command interrupted by user"
        
        finally:
            # Restore terminal settings
            if old_settings:
                try:
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
                except:
                    pass
            
            # Close master fd
            try:
                os.close(master_fd)
            except:
                pass
        
        # Wait for process to complete
        return_code = process.wait()
        
        # Combine all output
        full_output = ''.join(output_buffer).strip()
        
        return return_code == 0, full_output
            
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        return False, str(e)

rejudge = False
rejudge_count = 0
retry_count = 0
max_retries = SETTINGS.get("max_retries", 10)
user_input = ""
original_request = ""  # Track the original user request
conversation_history = []  # Track conversation for context
ai_mode = SETTINGS.get("default_mode", "ai").lower() == "ai"  # True for AI mode, False for direct mode

if __name__ == "__main__":
    while True:
        try:
            if not rejudge:
                rejudge = False
                retry_count = 0
                
                # Display mode-specific prompt with current model
                if ai_mode:
                    model_name = get_current_response_model_name()
                    console.print(f"[bold blue]Matthy's AI Shell [AI - {model_name}] > [/bold blue]", end="")
                else:
                    console.print("[bold green]Matthy's AI Shell [Direct] > [/bold green]", end="")
                
                user_input = input().strip()

                # Handle exit commands
                if user_input.lower() in ["/exit", "exit", "quit", ";q", ":q", "/q"]:
                    # console.print("[yellow]Goodbye![/yellow]")
                    break

                # Handle clear command - clear terminal and reset conversation
                if user_input.lower() in ["/clear", "/new", "/reset", "/c", "clear"]:
                    # Clear the terminal
                    subprocess.run("clear", shell=True)
                    # Reset conversation history (keep only system prompt)
                    payload = [{"role": "system", "content": SYSTEM_PROMPT}]
                    continue

                # Handle payload display command
                if user_input.lower() in ["/p", "/payload"]:
                    console.print("\n[bold cyan]Current Conversation Payload:[/bold cyan]")
                    for i, message in enumerate(payload):
                        role_color = {
                            "system": "yellow",
                            "user": "green", 
                            "assistant": "blue"
                        }.get(message["role"], "white")
                        
                        console.print(f"\n[bold {role_color}][{i+1}] {message['role'].upper()}:[/bold {role_color}]")
                        content = message["content"]
                        # Truncate very long content for readability
                        truncate_length = SETTINGS.get("payload_truncate_length", 500)
                        if len(content) > truncate_length:
                            content = content[:truncate_length] + "... [truncated]"
                        console.print(Panel(content, border_style=role_color))
                    
                    console.print(f"\n[dim]Total messages: {len(payload)}[/dim]")
                    continue

                # Handle help command
                if user_input.lower() in ["/help", "/h", "help"]:
                    help_text = """[bold cyan]◆ Available Commands[/bold cyan]

[yellow]▸ Mode Control[/yellow]
  [green]/ai[/green]      Switch to AI mode (AI assists with commands)
  [green]/dr[/green]      Switch to Direct mode (execute commands directly)

[yellow]▸ Model Management[/yellow]
  [green]/models[/green]  List all available models
  [green]/model[/green]   Show current model configuration
  [green]/model[/green] [dim]<name>[/dim]  Switch both models (e.g., /model grok)
  [green]/model[/green] [dim]<resp>:<task>[/dim]  Use different models (e.g., /model grok:gemini)

[yellow]▸ Session[/yellow]
  [green]/clear[/green]   Clear terminal and reset conversation
  [green]/new[/green]     Same as /clear
  [green]/c[/green]       Same as /clear

[yellow]▸ Information[/yellow]
  [green]/help[/green]    Show this help
  [green]/h[/green]       Same as /help
  [green]/p[/green]       Show conversation payload

[yellow]▸ Exit[/yellow]
  [green]/exit[/green]    Exit the shell
  [green]/q[/green]       Same as /exit

[dim italic]AI mode: Assistant helps execute commands
Direct mode: Commands run immediately[/dim italic]"""
                    console.print(Panel(help_text, title="Help", border_style="cyan"))
                    continue

                # Handle model switching commands
                if user_input.lower() in ["/models", "/model", "/m"]:
                    list_models()
                    continue
                elif user_input.lower().startswith("/model "):
                    model_alias = user_input[7:].strip()
                    switch_model(model_alias)
                    continue

                # Handle mode switching commands
                if user_input.lower() == "/ai":
                    ai_mode = True
                    # console.print("[blue]Switched to AI mode[/blue]")
                    continue
                elif user_input.lower() == "/dr":
                    ai_mode = False
                    # console.print("[green]Switched to Direct mode[/green]")
                    continue

                # Handle direct mode commands
                if not ai_mode:
                    # Execute command directly without AI intervention
                    success, result = execute_command(user_input)
                    # Don't print result - it's already shown in real-time
                    # Only show error indicator for failed commands
                    if not success:
                        console.print(f"[red]✗ Command failed[/red]")
                    continue

                # AI mode - add to payload for AI processing
                payload.append({"role": "user", "content": user_input})
                
                # Set original request only if this is a new conversation (not a continuation)
                if not rejudge:
                    original_request = user_input
                    conversation_history = []  # Reset conversation history for new task

            reply, reasoning = get_chat_response(client, payload)

            # Parse command blocks from the response
            command_pattern = re.compile(r"```command\s*(.*?)\s*```", re.DOTALL)
            commands = command_pattern.findall(reply)
            
            if commands:
                # Check if there are multiple commands (forbidden)
                if len(commands) > 1:
                    console.print(f"[red]Multiple commands detected ({len(commands)} commands). Asking AI to correct.[/red]")
                    payload.append({"role": "assistant", "content": reply})
                    payload.append({
                        "role": "system", 
                        "content": f"You provided {len(commands)} commands in one response, which is forbidden. You must provide EXACTLY ONE command per response. Please choose the FIRST command you need to execute and provide it alone with explanation."
                    })
                    rejudge = True
                    rejudge_count += 1
                    if rejudge_count > 3:
                        console.print(f"[red]Too many multiple command violations. Resetting conversation.[/red]")
                        payload = [{"role": "system", "content": SYSTEM_PROMPT}]
                        rejudge = False
                        rejudge_count = 0
                    continue
                
                # Response contains exactly one command - process it
                payload.append({"role": "assistant", "content": reply})
                rejudge = False
                rejudge_count = 0
                
                # Display the full response with explanations
                md = Markdown(reply)
                console.print()  # Empty line before
                console.print(Panel(md, title="Response", border_style="blue"))
                console.print()  # Empty line after
                
                # Process the single command (we enforce exactly one command per response)
                command = commands[0].strip()
                if not command:
                    console.print("[yellow]Empty command block detected.[/yellow]")
                    continue
                    
                # # Ask for confirmation with aesthetic panel that includes the prompt
                # console.print()  # Empty line before
                
                # Create a custom prompt within the panel
                panel_content = f"[bold white]Execute command:[/bold white] [cyan]`{command}`[/cyan]\n\n[yellow]Proceed? [y/n] (y):[/yellow] "
                
                # Print the panel with the prompt
                console.print(Panel(panel_content, 
                                  title="[yellow]Command[/yellow]", 
                                  border_style="yellow"), end="")
                
                # Get user input directly without Rich's Prompt
                user_choice = input().strip().lower()
                if not user_choice:
                    user_choice = "y"  # Default to yes
                
                confirm = user_choice
                if confirm.lower() == "n":
                    # User declined - ask for reason and get alternative
                    reason = Prompt.ask("Reason for decline")
                    feedback_context = f"User declined to run the command: {command}\nReason: {reason}\n\nPlease provide an alternative approach to complete the original request: {original_request}"
                    payload.append({"role": "user", "content": feedback_context})
                    rejudge = True
                else:
                    # Execute the command
                    success, result = execute_command(command)
                    
                    # Only show panel for errors - success output is already shown in real-time
                    if not success and result.strip():
                        console.print()  # Empty line before
                        console.print(Panel(result, title=f"Error: {command}", border_style="red"))
                        console.print()  # Empty line after

                    # Track conversation
                    conversation_history.append(f"Command: {command}")
                    conversation_history.append(f"Output: {result}")
                    conversation_history.append(f"Success: {success}")
                    
                    # Keep conversation history manageable (last 10 entries)
                    if len(conversation_history) > 10:
                        conversation_history = conversation_history[-10:]
                    
                    # Check if the overall task is complete
                    conversation_context = "\n".join(conversation_history)
                    task_status = check_task_status(client, original_request, conversation_context)
                    
                    if "[CONTINUE]" in task_status:
                        # Task needs more steps - let AI continue
                        continue_context = f"Command executed: {command}\nOutput: {result}\nSuccess: {success}\n\nThe original request ({original_request}) is not yet complete. Please continue with the next step."
                        payload.append({"role": "user", "content": continue_context})
                        rejudge = True
                    elif "[FAILED]" in task_status:
                        # Task failed - provide summary
                        if retry_count < max_retries:
                            retry_count += 1
                            failure_context = f"Command executed but task status is failed.\nCommand: {command}\nOutput: {result}\nSuccess: {success}\nStatus: {task_status}\n\nPlease try a different approach to complete: {original_request}"
                            payload.append({"role": "user", "content": failure_context})
                            rejudge = True
                        else:
                            console.print(f"[yellow]Maximum retry attempts ({max_retries}) reached.[/yellow]")
                            retry_choice = Prompt.ask("Do you want to continue trying?", choices=["Y", "N"], default="N")
                            if retry_choice == "Y":
                                retry_count = 0  # Reset retry count
                                failure_context = f"Command executed but failed.\nCommand: {command}\nOutput: {result}\nSuccess: {success}\nStatus: {task_status}\n\nUser requested to continue trying. Please try a different approach to complete: {original_request}"
                                payload.append({"role": "user", "content": failure_context})
                                rejudge = True
                            else:
                                payload.append({"role": "user", "content": f"Task failed after {max_retries} attempts and user chose to stop. Please provide a summary of what was attempted and suggest alternatives."})
                                rejudge = True
                                retry_count = 0
                    else:  # [COMPLETE]
                        # Task is complete - ask for summary
                        payload.append({"role": "user", "content": f"Task completed. Please provide a brief summary of what was accomplished for: {original_request}."})
                        rejudge = True
                        retry_count = 0
            else:
                # No commands found - this is a direct text response
                payload.append({"role": "assistant", "content": reply})
                rejudge = False
                rejudge_count = 0
                
                # Display as a direct reply
                md = Markdown(reply)
                console.print()  # Empty line before
                console.print(Panel(md, title="Summary", border_style="blue"))
                console.print()  # Empty line after
                
                # Check if this is a question requiring user input or if task is complete
                conversation_history.append(f"AI Reply: {reply}")
                
                # # Keep conversation history manageable (last 10 entries)
                # if len(conversation_history) > 10:
                #     conversation_history = conversation_history[-10:]
                
                # Use AI to check if this is a question requiring user input
                is_question = check_if_question(client, reply)
                
                if not is_question:
                    # Not a question, check if task is complete
                    conversation_context = "\n".join(conversation_history)
                    task_status = check_task_status(client, original_request, conversation_context)
                    
                    if "[CONTINUE]" in task_status:
                        # Task needs more steps - let AI continue
                        continue_context = f"The original request ({original_request}) is not yet complete. Please continue with the next step."
                        payload.append({"role": "user", "content": continue_context})
                        rejudge = True
                    # If COMPLETE or FAILED, just end naturally (no rejudge)
                # If it's a question, don't check completion - wait for user response

        except KeyboardInterrupt:
            console.print("\n[yellow]Use /exit to quit the program[/yellow]")
            continue
        except Exception as error:
            console.print(f"[red]Error occurred:[/red] {str(error)}")
            continue
