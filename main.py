#!/usr/bin/env python

# This is a Python script that uses the OpenAI API to interact with a Linux terminal.
# It is designed to be an agentic ai assistant that can execute commands and provide
# explanations based on the user's input.

# This script is split into several other files for better organization. Add new code to the relevant files.

import sys
import os
import re
import subprocess
import time
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import load_config
from src.models import ModelManager
from src.chat import ChatManager
from src.ui import UIManager
from src.commands import execute_command, get_prompt_directory
from src.conversation_manager import ConversationManager

def main():
    """Main entry point for the AI Shell Assistant"""
    
    # Initialize components
    ui = UIManager()
    
    try:
        # Load configuration
        config = load_config()
        
        # Initialize managers
        model_manager = ModelManager(config)
        conversation_manager = ConversationManager(config)
        chat_manager = ChatManager(config, model_manager, conversation_manager)
        
        # Check for conversation resume
        resume_session = conversation_manager.check_for_resume()
        if resume_session:
            # Resume the previous conversation
            resumed_payload = conversation_manager.resume_session(resume_session)
            chat_manager.payload = resumed_payload
        
        # Settings
        settings = config.get("settings", {})
        max_retries = settings.get("max_retries", 10)
        ai_mode = settings.get("default_mode", "ai").lower() == "ai"
        
        # Variables for conversation tracking
        rejudge = False
        rejudge_count = 0
        retry_count = 0
        original_request = ""
        conversation_history = []
        
        # Show welcome message if enabled in config
        if settings.get("show_welcome_message", True):
            ui.show_welcome()
        
        # Main interaction loop
        user_input = ""
        while True:
            try:
                if not rejudge:
                    rejudge = False
                    retry_count = 0
                    
                    # Display mode-specific prompt with current model and directory
                    current_dir = get_prompt_directory()
                    if ai_mode:
                        model_name = model_manager.get_model_display_name(model_manager.current_model)
                        ui.console.print(f"[bold blue]AI Shell [AI - {model_name}] [dim cyan]{current_dir}[/dim cyan] > [/bold blue]", end="")
                    else:
                        ui.console.print(f"[bold green]AI Shell [Direct] [dim cyan]{current_dir}[/dim cyan] > [/bold green]", end="")
                    
                    user_input = input().strip()

                    # Handle exit commands
                    if user_input.lower() in ["/exit", "exit", "quit", ";q", ":q", "/q"]:
                        conversation_manager.save_and_exit()
                        break

                    # Handle clear command
                    if user_input.lower() in ["/clear", "/new", "/reset", "/c", "clear"]:
                        subprocess.run("clear", shell=True)
                        chat_manager.clear_history()
                        continue

                    # Handle payload display command
                    if user_input.lower() in ["/p", "/payload"]:
                        ui.console.print("\n[bold cyan]Current Conversation Payload:[/bold cyan]")
                        for i, message in enumerate(chat_manager.payload):
                            role_color = {
                                "system": "yellow",
                                "user": "green", 
                                "assistant": "blue"
                            }.get(message["role"], "white")
                            
                            ui.console.print(f"\n[bold {role_color}][{i+1}] {message['role'].upper()}:[/bold {role_color}]")
                            content = message["content"]
                            truncate_length = settings.get("payload_truncate_length", 500)
                            if len(content) > truncate_length:
                                content = content[:truncate_length] + "... [truncated]"
                            ui.console.print(Panel(content, border_style=role_color))
                        
                        ui.console.print(f"\n[dim]Total messages: {len(chat_manager.payload)}[/dim]")
                        continue

                    # Handle help command
                    # Handle help command
                    if user_input.lower() in ["/help", "/h", "help"]:
                        ui.show_help()
                        continue

                    # Handle conversation management commands
                    if user_input.lower() in ["/save"]:
                        conversation_manager.save_conversation()
                        continue
                    elif user_input.lower().startswith("/save "):
                        name = user_input[6:].strip()
                        conversation_manager.save_conversation(name)
                        continue
                    elif user_input.lower() in ["/load"]:
                        new_payload = conversation_manager.load_conversation()
                        if new_payload is not None:
                            chat_manager.payload = new_payload
                        continue
                    elif user_input.lower().startswith("/load "):
                        name = user_input[6:].strip()
                        new_payload = conversation_manager.load_conversation(name)
                        if new_payload is not None:
                            chat_manager.payload = new_payload
                        continue
                    elif user_input.lower() in ["/conversations", "/cv"]:
                        conversation_manager.list_conversations()
                        continue
                    elif user_input.lower() == "/archive":
                        if conversation_manager.archive_conversation():
                            chat_manager.clear_history()
                        continue
                    elif user_input.lower().startswith("/delete "):
                        name = user_input[8:].strip()
                        conversation_manager.delete_conversation(name)
                        continue
                    elif user_input.lower() == "/status":
                        status = conversation_manager.get_status_info()
                        ui.console.print(f"\n[bold cyan]Conversation Status:[/bold cyan]")
                        ui.console.print(f"Session ID: {status['session_id']}")
                        ui.console.print(f"Started: {status['started_at']}")
                        ui.console.print(f"Messages: {status['message_count']}")
                        ui.console.print(f"Interactions: {status['interactions']}")
                        ui.console.print(f"Status: {status['status']}")
                        if status['original_request']:
                            ui.console.print(f"Original request: {status['original_request']}")
                        continue

                    # Handle model commands
                    if user_input.lower() in ["/models", "/model", "/m"]:
                        model_manager.list_models()
                        continue
                    elif user_input.lower().startswith("/model "):
                        model_alias = user_input[7:].strip()
                        model_manager.switch_model(model_alias)
                        continue

                    # Handle mode switching commands
                    if user_input.lower() == "/ai":
                        ai_mode = True
                        continue
                    elif user_input.lower() == "/dr":
                        ai_mode = False
                        continue

                    # Handle direct mode commands
                    if not ai_mode:
                        success, result = execute_command(user_input)
                        if not success and result.strip():
                            ui.console.print(f"[red]✗ Command failed[/red]")
                        continue

                    # Set original request for new conversations
                    if not rejudge:
                        original_request = user_input
                        conversation_history = []

                # AI mode - add to payload for AI processing
                # AI mode - add to payload for AI processing
                if not rejudge:
                    # Add new user input to conversation payload
                    chat_manager.payload.append({"role": "user", "content": user_input})
                    # Update conversation manager with new payload
                    conversation_manager.update_payload(chat_manager.payload, original_request)
                else:
                    # Rejudge mode - continuing from previous context, no new user input needed
                    pass
                    
                # Generate AI response from current conversation context
                # This will show "Processing..." then "Thinking..." status messages
                response, reasoning = chat_manager.get_response_without_user_input()
                
                if not response:
                    # Response was interrupted or failed, reset state and continue
                    rejudge = False
                    rejudge_count = 0
                    retry_count = 0
                    continue
                
                # Check if response is just whitespace or empty
                if not response.strip():
                    ui.console.print("[yellow]AI provided empty response - treating as task completion signal.[/yellow]")
                    
                    # If we have an original request, this might be a completion signal
                    if original_request:
                        # Add a completion summary request
                        chat_manager.payload.append({
                            "role": "user", 
                            "content": f"Task appears to be complete for: {original_request}. Please provide a brief summary of what was accomplished."
                        })
                        rejudge = True
                        # Clear original_request to prevent loops
                        original_request = ""
                    else:
                        # No original request context - ask for clarification
                        chat_manager.payload.append({
                            "role": "user", 
                            "content": "You provided an empty response. Please provide a proper response or explain why you cannot proceed."
                        })
                        rejudge = True
                    continue

                # Parse command blocks from the response
                command_pattern = re.compile(r"```command\s*(.*?)\s*```", re.DOTALL)
                commands = command_pattern.findall(response)
                
                if commands:
                    # Check if there are multiple commands (forbidden)
                    if len(commands) > 1:
                        ui.console.print(f"[red]Multiple commands detected ({len(commands)} commands). Asking AI to correct.[/red]")
                        chat_manager.payload.append({
                            "role": "user", 
                            "content": f"You provided {len(commands)} commands in one response, which is forbidden. You must provide EXACTLY ONE command per response. Please choose the FIRST command you need to execute and provide it alone with explanation."
                        })
                        rejudge = True
                        rejudge_count += 1
                        if rejudge_count > 3:
                            ui.console.print(f"[red]Too many multiple command violations. Resetting conversation.[/red]")
                            chat_manager.clear_history()
                            rejudge = False
                            rejudge_count = 0
                        continue
                    
                    # Response contains exactly one command - process it
                    rejudge = False
                    rejudge_count = 0
                    
                    # Display the full response with explanations
                    md = Markdown(response)
                    ui.console.print()
                    ui.console.print(Panel(md, title="Response", border_style="blue"))
                    ui.console.print()
                    
                    # Process the single command
                    command = commands[0].strip()
                    if not command:
                        ui.console.print("[yellow]Empty command block detected.[/yellow]")
                        continue
                    
                    # Ask for confirmation
                    panel_content = f"[bold white]Execute command:[/bold white] [cyan]`{command}`[/cyan]\n\n[yellow]Proceed? [y/n] (y):[/yellow] "
                    ui.console.print(Panel(panel_content, title="[yellow]Command[/yellow]", border_style="yellow"), end="")
                    
                    user_choice = input().strip().lower()
                    if not user_choice:
                        user_choice = "y"
                    
                    if user_choice.lower() == "n":
                        reason = Prompt.ask("Reason for decline")
                        feedback_context = f"User declined to run the command: {command}\nReason: {reason}\n\nPlease provide an alternative approach to complete the original request: {original_request}"
                        chat_manager.payload.append({"role": "user", "content": feedback_context})
                        rejudge = True
                    else:
                        # Execute the command
                        success, result = execute_command(command)
                        
                        if not success and result.strip():
                            ui.console.print()
                            ui.console.print(Panel(result, title=f"Error: {command}", border_style="red"))
                            ui.console.print()

                        # Track conversation
                        conversation_history.append(f"Command: {command}")
                        conversation_history.append(f"Output: {result}")
                        conversation_history.append(f"Success: {success}")
                        
                        if len(conversation_history) > 10:
                            conversation_history = conversation_history[-10:]
                        
                        # Check if the task is complete by analyzing command output against original request
                        # This will show "Checking..." status message
                        completed, reason = chat_manager.check_task_status(result, original_request)

                        # Provide feedback to the AI based on task completion status
                        if completed is False:
                            # Task needs more steps - prepare context for AI to continue
                            continue_context = f"Command executed: {command}\nOutput: {result}\nSuccess: {success}\n\nThe original request ({original_request}) is not yet complete. Please continue with the next step."
                            chat_manager.payload.append({"role": "user", "content": continue_context})
                            rejudge = True
                        elif completed is None:
                            # Task failed
                            if retry_count < max_retries:
                                retry_count += 1
                                with ui.console.status("[bold yellow]Preparing retry...[/bold yellow]", spinner_style="yellow"):
                                    failure_context = f"Command executed but task status check failed.\nCommand: {command}\nOutput: {result}\nSuccess: {success}\n\nPlease try a different approach to complete: {original_request}"
                                    chat_manager.payload.append({"role": "user", "content": failure_context})
                                rejudge = True
                            else:
                                ui.console.print(f"[yellow]Maximum retry attempts ({max_retries}) reached.[/yellow]")
                                retry_choice = Prompt.ask("Do you want to continue trying?", choices=["Y", "N"], default="N")
                                if retry_choice == "Y":
                                    retry_count = 0
                                    with ui.console.status("[bold yellow]Preparing retry...[/bold yellow]", spinner_style="yellow"):
                                        failure_context = f"Command executed but failed.\nCommand: {command}\nOutput: {result}\nSuccess: {success}\n\nUser requested to continue trying. Please try a different approach to complete: {original_request}"
                                        chat_manager.payload.append({"role": "user", "content": failure_context})
                                    rejudge = True
                                else:
                                    with ui.console.status("[bold red]Preparing summary...[/bold red]", spinner_style="red"):
                                        chat_manager.payload.append({"role": "user", "content": f"Task failed after {max_retries} attempts and user chose to stop. Please provide a summary of what was attempted and suggest alternatives."})
                                    rejudge = True
                                    retry_count = 0
                        else:
                            # Task is complete
                            with ui.console.status("[bold green]Preparing summary...[/bold green]", spinner_style="green"):
                                chat_manager.payload.append({"role": "user", "content": f"Task completed. Please provide a brief summary of what was accomplished for: {original_request}."})
                            rejudge = True
                            retry_count = 0
                            # Clear original_request to prevent re-feeding it
                            original_request = ""
                else:
                    # No commands found - direct text response
                    rejudge = False
                    rejudge_count = 0
                    
                    # Display as a direct reply
                    md = Markdown(response)
                    ui.console.print()
                    ui.console.print(Panel(md, title="Summary", border_style="blue"))
                    ui.console.print()
                    
                    # Check if this is a question requiring user input or if task needs to continue
                    if original_request:  # Only check if we have an original request to complete
                        conversation_history.append(f"AI Reply: {response}")
                        
                        # Keep conversation history manageable (last 10 entries)
                        if len(conversation_history) > 10:
                            conversation_history = conversation_history[-10:]
                        
                        # Use AI to check if this is a question requiring user input
                        is_question = chat_manager.check_if_question(response)
                        
                        if not is_question:
                            # Not a question, check if task is complete
                            conversation_context = "\n".join(conversation_history)
                            completed, reason = chat_manager.check_task_status(conversation_context, original_request)
                            
                            if completed is False:  # Task needs more steps
                                continue_context = f"The original request ({original_request}) is not yet complete. Please continue with the next step."
                                chat_manager.payload.append({"role": "user", "content": continue_context})
                                rejudge = True
                            # If completed is True or None, just end naturally (no rejudge)
                        # If it's a question, don't check completion - wait for user response
                
            except KeyboardInterrupt:
                # ui.console.print("\n[yellow]Use /exit to quit the program[/yellow]")
                ui.console.print("")
                continue
            except EOFError:
                ui.console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as error:
                ui.console.print(f"[red]Error occurred:[/red] {str(error)}")
                continue
                
    except Exception as e:
        ui.show_error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
