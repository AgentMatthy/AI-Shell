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
            # New multi-model format
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
        else:
            # Legacy single model format - convert to new format
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
                "default": "default",
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
current_model = MODELS["default"]

# System prompt
SYSTEM_PROMPT = """
You are a Linux terminal assistant Agent. Please strictly follow the rules below:

Rules:

1. When the user requests something that requires system operations, generate the corresponding terminal command (ensure Bash compatibility)
2. If tasked with something that requires mulltiple commands, do them one by one. Only output one command as a response, or chain them together with '&&'.
2. DO NOT use markdown tags in the output
3. The output format must always be JSON, structured as follows:

{
  "action": "execute_command",
  "command": "ls -l",
  "explanation": "List detailed information of the current directory using the ls tool"
}

or

{
  "action": "direct_reply",
  "content": "Hello, how can I help you?"
}

For new lines, use '\\n'.
"""

# Initialize Rich components
console = Console()

# Initialize OpenAI client
client = OpenAI(api_key=API_CONFIG["api_key"], base_url=API_CONFIG["url"])

payload = [{"role": "system", "content": SYSTEM_PROMPT}]

def get_current_model_name():
    """Get the current model's display name"""
    if current_model in MODELS["available"]:
        return MODELS["available"][current_model]["display_name"]
    return current_model

def get_current_model_api_name():
    """Get the current model's API name"""
    if current_model in MODELS["available"]:
        return MODELS["available"][current_model]["name"]
    return current_model

def list_models():
    """Display available models"""
    console.print("\n[bold cyan]Available models:[/bold cyan]")
    for alias, model_info in MODELS["available"].items():
        marker = "[*]" if alias == current_model else "[ ]"
        display_name = model_info["display_name"]
        console.print(f"  {marker} [yellow]{alias}[/yellow] - {display_name}")
    console.print()

def switch_model(model_alias):
    """Switch to a different model"""
    global current_model
    
    if model_alias not in MODELS["available"]:
        console.print(f"[red]Error: Model '{model_alias}' not found.[/red]")
        console.print("[yellow]Use /models to see available models.[/yellow]")
        return False
    
    current_model = model_alias
    model_info = MODELS["available"][current_model]
    console.print(f"[green]Switched to {model_info['display_name']}[/green]")
    return True

def check_result(model_client, user_input, command_output) -> str:
    prompt = f"""
You are a task verification assistant. Based on the following information, determine whether the command met the user's expectations.
If the request is a question, and the command output contains the answer, it counts as a success.

User request: {user_input}
Command output: {command_output}

Please answer:
- If the expectation is met, output "[✅] Success"
- If not, output "[❌] Failure: Reason"
    """
    response = model_client.chat.completions.create(
        model=get_current_model_api_name(),
        messages=[{"role": "system", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def get_chat_response(client: OpenAI, payload: list) -> tuple[str, str]:
    """Get chat response"""
    response = client.chat.completions.create(
        model=get_current_model_api_name(), messages=payload, stream=True
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
    """Execute the command and return its output."""
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout_bytes, stderr_bytes = process.communicate()
        stdout = decode_output(stdout_bytes)
        stderr = decode_output(stderr_bytes)

        if process.returncode == 0:
            return True, stdout
        else:
            error_output = stderr if stderr.strip() else stdout
            return False, error_output.strip()
    except Exception as e:
        return False, str(e)

rejudge = False
rejudge_count = 0
retry_count = 0
max_retries = SETTINGS.get("max_retries", 10)
user_input = ""
ai_mode = SETTINGS.get("default_mode", "ai").lower() == "ai"  # True for AI mode, False for direct mode

if __name__ == "__main__":
    while True:
        try:
            if not rejudge:
                rejudge = False
                retry_count = 0
                
                # Display mode-specific prompt with current model
                if ai_mode:
                    model_name = get_current_model_name()
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
                    # console.print("[green]Terminal cleared and conversation reset![/green]")
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
                    help_text = """
[bold cyan]Available Commands:[/bold cyan]

[yellow]Mode Control:[/yellow]
  /ai          - Switch to AI mode (AI assists with commands)
  /dr          - Switch to Direct mode (execute commands directly)

[yellow]Model Management:[/yellow]
  /models      - List all available models
  /model       - Show current model and available models
  /model <name> - Switch to a specific model (e.g., /model grok)

[yellow]Session Management:[/yellow]
  /clear       - Clear terminal and reset conversation
  /new         - Same as /clear
  /reset       - Same as /clear
  /c           - Same as /clear

[yellow]Information:[/yellow]
  /help        - Show this help message
  /h           - Same as /help
  /p           - Show current conversation payload
  /payload     - Same as /p

[yellow]Exit:[/yellow]
  /exit        - Exit the shell
  /q           - Same as /exit
  exit         - Same as /exit
  quit         - Same as /exit

[dim]Note: In AI mode, the assistant will help you execute commands.
In Direct mode, commands are executed immediately without AI assistance.[/dim]
                    """
                    console.print(help_text)
                    continue

                # Handle model switching commands
                if user_input.lower() in ["/models", "/model"]:
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
                    # console.print(f"[bold yellow]Executing:[/bold yellow] {user_input}")
                    success, result = execute_command(user_input)
                    if success:
                        print(result)
                    else:
                        console.print(f"[red]Error:[/red] {result}")
                    continue

                # AI mode - add to payload for AI processing
                payload.append({"role": "user", "content": user_input})

            reply, reasoning = get_chat_response(client, payload)

            try:
                # Extract JSON from code blocks or use reply directly
                pattern = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
                json_match = pattern.search(reply)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    json_str = reply.strip()
                
                # Try to parse the JSON
                command = json.loads(json_str)
                payload.append({"role": "assistant", "content": reply})
                rejudge = False
                rejudge_count = 0
                
                if command["action"] == "execute_command":
                    # Display command in a panel like answers
                    command_content = f"**Command:** `{command['command']}`\n\n{command.get('explanation', '')}"
                    md = Markdown(command_content)
                    console.print(Panel(md, title="Execute Command", border_style="yellow"))

                    confirm = Prompt.ask("Run?", choices=["Y", "N"], default="Y")

                    if confirm == "Y":
                        success, result = execute_command(command["command"])
                        print("\n" + result)

                        # Add verification logic
                        verification = check_result(client, user_input, result)
                        # console.print(f"[dim]Verification result: {verification}[/dim]")

                        # Check if the task failed and retry if needed
                        if "[❌] Failure:" in verification and retry_count < max_retries:
                            retry_count += 1
                            # console.print(f"[yellow]Task failed. Attempting retry {retry_count}/{max_retries}...[/yellow]")
                            
                            # Add failure context to payload for the AI to learn from
                            failure_context = f"The previous command '{command['command']}' failed. Output: {result}. Verification: {verification}. Please try a different approach to complete the user's request: {user_input}"
                            payload.append({"role": "user", "content": failure_context})
                            rejudge = True  # Let the AI try again with a different approach
                            continue
                        elif "[❌] Failure:" in verification and retry_count >= max_retries:
                            console.print(f"[red]Maximum retry attempts ({max_retries}) reached. Task could not be completed.[/red]")
                            retry_count = 0
                            # Ask AI to provide failure summary
                            payload.append({"role": "assistant", "content": result + "\nVerification result: " + verification})
                            payload.append(
                                {
                                    "role": "user",
                                    "content": "The task could not be completed after multiple attempts. Please provide a summary of what was attempted and suggest alternative solutions using the direct reply template.",
                                }
                            )
                            rejudge = True
                        else:
                            # console.print(f"[green]Task completed successfully![/green]")
                            retry_count = 0
                            # Ask AI to provide success summary
                            payload.append({"role": "assistant", "content": result + "\nVerification result: " + verification})
                            payload.append(
                                {
                                    "role": "user",
                                    "content": "The task has been completed successfully! Please provide a brief summary of what was accomplished and the final result using the direct reply template. Do not repeat that the task was successful, but if there was a question, answer it.",
                                }
                            )
                            rejudge = True  # Set the flag to let the LLM handle this summary request in the next round
                    else:
                        console.print("[yellow]Execution cancelled[/yellow]")
                        payload.append({"role": "assistant", "content": "Execution cancelled"})

                elif command["action"] == "direct_reply":
                    # Direct reply with Markdown formatting
                    md = Markdown(command["content"])
                    console.print(Panel(md, title="Reply", border_style="blue"))

            except json.JSONDecodeError:
                console.print(f"[red]Unable to parse result:[/red]\n {reply}")
                payload.append(
                    {
                        "role": "system",
                        "content": "Please provide a reply in the correct format (JSON only, no markdown tags).",
                    }
                )
                rejudge = True
                rejudge_count += 1
                if rejudge_count > 3:
                    print(f"[red] [!] Too many parsing failures, exiting![/red]")
                    break

        except KeyboardInterrupt:
            console.print("\n[yellow]Use /exit to quit the program[/yellow]")
            continue
        except Exception as error:
            console.print(f"[red]Error occurred:[/red] {str(error)}")
            continue

