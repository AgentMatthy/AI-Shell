#!/usr/bin/env python

import os
import sys
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from .constants import (
    CONFIG_FILE_PATH, CONTEXT_FILE_PATH,
    DEFAULT_PROMPT_SECTIONS, DEFAULT_PROMPT_SECTIONS_DIRECT,
    DEFAULT_PROMPT_SECTIONS_INCOGNITO,
)


def run_setup_wizard(console: Console) -> Dict[str, Any]:
    """Run the interactive setup wizard for first-time configuration"""
    console.print(Panel(
        "[bold cyan]Welcome to AI Shell Setup Wizard[/bold cyan]\n\n"
        "This wizard will help you configure your AI Shell installation.",
        border_style="cyan"
    ))
    console.print()
    
    # Step 1: Choose preset
    console.print("[bold yellow]Step 1: Choose Configuration Preset[/bold yellow]")
    console.print("  [cyan]openrouter[/cyan] - Use OpenRouter.ai (recommended, access to many models)")
    console.print("  [cyan]custom[/cyan]     - Use a custom OpenAI-compatible API endpoint")
    console.print()
    
    preset = Prompt.ask(
        "Select preset",
        choices=["openrouter", "custom"],
        default="openrouter"
    )
    
    # Step 2: Get API configuration based on preset
    console.print()
    console.print("[bold yellow]Step 2: API Configuration[/bold yellow]")
    
    if preset == "openrouter":
        api_url = "https://openrouter.ai/api/v1"
        console.print(f"[dim]Using OpenRouter API: {api_url}[/dim]")
        api_key = Prompt.ask("Enter your OpenRouter API key", password=True)
        
        # Default models for OpenRouter
        models_config = {
            "response_model": "gemini-pro",
            "available": {
                "gemini-pro": {
                    "name": "google/gemini-3-pro-preview",
                    "alias": "gemini-pro",
                    "display_name": "Gemini 3 Pro"
                },
                "claude-sonnet": {
                    "name": "anthropic/claude-sonnet-4.5",
                    "alias": "claude-sonnet",
                    "display_name": "Claude Sonnet 4.5"
                },
                "claude-haiku": {
                    "name": "anthropic/claude-haiku-4.5",
                    "alias": "claude-haiku",
                    "display_name": "Claude Haiku 4.5"
                },
                "grok-fast": {
                    "name": "x-ai/grok-4.1-fast",
                    "alias": "grok-fast",
                    "display_name": "Grok 4.1 Fast"
                },
                "glm": {
                    "name": "z-ai/glm-4.6",
                    "alias": "glm",
                    "display_name": "GLM 4.6"
                },
                "gpt": {
                    "name": "openai/gpt-5.1",
                    "alias": "gpt",
                    "display_name": "GPT 5.1"
                }
            }
        }
    else:
        # Custom API configuration
        api_url = Prompt.ask("Enter API URL (OpenAI-compatible endpoint)")
        api_key = Prompt.ask("Enter API key", password=True)
        
        console.print()
        console.print("[bold yellow]Step 2b: Main Model Configuration[/bold yellow]")
        model_id = Prompt.ask("Enter model ID (e.g., gpt-4, claude-3-opus)")
        model_display_name = Prompt.ask("Enter display name for the model", default=model_id)
        
        models_config = {
            "response_model": "main",
            "available": {
                "main": {
                    "name": model_id,
                    "alias": "main",
                    "display_name": model_display_name
                }
            }
        }
    
    # Step 3: Web Search Model (optional)
    console.print()
    console.print("[bold yellow]Step 3: Web Search Configuration (Optional)[/bold yellow]")
    console.print("[dim]Web search uses a search-capable AI model (e.g. perplexity/sonar-pro) to answer queries.[/dim]")
    console.print("[dim]This uses your existing API endpoint - no extra API key needed.[/dim]")
    console.print()
    
    search_model = Prompt.ask("Enter search model ID (e.g. perplexity/sonar-pro, leave empty to disable)", default="perplexity/sonar-pro")
    
    # Step 4: Context information
    console.print()
    console.print("[bold yellow]Step 4: System Context[/bold yellow]")
    console.print("[dim]Provide information to help the AI understand your system.[/dim]")
    console.print("[dim]Examples: OS version, preferred package manager, shell, common tools, etc.[/dim]")
    console.print()
    
    context_info = Prompt.ask(
        "Enter system context (or press Enter for a simple prompt)",
        default=""
    )
    
    if not context_info:
        # Provide a more guided approach
        console.print()
        console.print("[dim]Let's gather some basic info:[/dim]")
        os_info = Prompt.ask("Operating System", default="Linux")
        package_manager = Prompt.ask("Preferred package manager", default="apt")
        shell = Prompt.ask("Shell", default="bash")
        extra_info = Prompt.ask("Any other relevant info (optional)", default="")
        
        context_info = f"""# System Context

## Operating System
{os_info}

## Package Manager
{package_manager}

## Shell
{shell}
"""
        if extra_info:
            context_info += f"""
## Additional Information
{extra_info}
"""
    else:
        context_info = f"""# System Context

{context_info}
"""
    
    # Build the configuration dictionary
    config = {
        "api": {
            "url": api_url,
            "api_key": api_key
        },
        "web_search": {
            "enabled": bool(search_model),
            "model": search_model,
            "api_url": "",
            "api_key": "",
            "system_prompt": ""
        },
        "models": models_config,
        "settings": {
            "max_retries": 30,
            "payload_truncate_length": 1500,
            "default_mode": "ai",
            "show_welcome_message": False
        },
        "conversations": {
            "auto_save_interval": 1,
            "max_recent": 10,
            "resume_on_startup": True,
            "storage_path": "~/.ai-shell/conversations"
        },
        "incognito": {
            "enabled": True,
            "api": {
                "url": "http://localhost:11434/v1",
                "api_key": "ollama"
            },
            "model": {
                "name": "artifish/llama3.2-uncensored",
                "display_name": "Llama 3.2 Uncensored"
            }
        }
    }
    
    # Write the configuration file
    config_path = CONFIG_FILE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    console.print(f"\n[green]✓ Configuration saved to {config_path}[/green]")
    
    # Write the context file
    context_path = CONTEXT_FILE_PATH
    with open(context_path, 'w') as f:
        f.write(context_info)
    
    console.print(f"[green]✓ Context saved to {context_path}[/green]")
    
    console.print()
    console.print(Panel(
        "[bold green]Setup Complete![/bold green]\n\n"
        "You can now use AI Shell. To reconfigure, run [cyan]/resetconfig[/cyan]",
        border_style="green"
    ))
    console.print()
    
    return config


def reset_config() -> Optional[Dict[str, Any]]:
    """Reset configuration by running the setup wizard again"""
    console = Console()
    
    # Check if config exists and confirm reset
    if CONFIG_FILE_PATH.exists() or CONTEXT_FILE_PATH.exists():
        if not Confirm.ask("[yellow]This will overwrite your existing configuration. Continue?[/yellow]"):
            console.print("[dim]Configuration reset cancelled.[/dim]")
            return None
    
    # Run the setup wizard
    return run_setup_wizard(console)


def load_config(config_path: Path = CONFIG_FILE_PATH) -> Optional[Dict[str, Any]]:
    """Load and validate configuration from YAML file"""
    console = Console()
    
    # Ensure the config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if both config and context files exist
    context_path = CONTEXT_FILE_PATH
    if not config_path.exists() or not context_path.exists():
        console.print("[yellow]Configuration not found. Starting setup wizard...[/yellow]")
        console.print()
        return run_setup_wizard(console)
    
    # Check if file is readable
    if not config_path.is_file() or not os.access(config_path, os.R_OK):
        console.print(f"[red]Error: Config file '{config_path}' is not readable![/red]")
        sys.exit(1)
    
    # Check file size (prevent loading massive files)
    try:
        file_size = config_path.stat().st_size
        if file_size > 1024 * 1024:  # 1MB limit
            console.print(f"[red]Error: Config file '{config_path}' is too large (>1MB)![/red]")
            sys.exit(1)
    except OSError as e:
        console.print(f"[red]Error accessing config file '{config_path}': {e}[/red]")
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Validate and normalize configuration
        config = _validate_and_normalize_config(config, console)
        
        return config
    except yaml.YAMLError as e:
        console.print(f"[red]Error: Invalid YAML in config file: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)

def _validate_and_normalize_config(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Validate and normalize configuration, converting legacy formats"""
    
    # Handle different config formats and convert to modern format
    if "models" in config:
        if "response_model" in config["models"]:
            # Modern format - validate required fields
            _validate_required_fields(config, console, [
                "api.url", "api.api_key", 
                "models.response_model"
            ])
        elif "default" in config["models"]:
            # Legacy multi-model format - convert to modern
            _validate_required_fields(config, console, [
                "api.url", "api.api_key", "models.default"
            ])
            
            default_model = config["models"]["default"]
            config["models"]["response_model"] = default_model
        else:
            console.print(f"[red]Error: Invalid models configuration format[/red]")
            sys.exit(1)
    else:
        # Legacy single model format - convert to modern
        _validate_required_fields(config, console, [
            "api.url", "api.api_key", "api.model"
        ])
        
        model_name = config["api"]["model"]
        config["models"] = {
            "response_model": "default",
            "available": {
                "default": {
                    "name": model_name,
                    "alias": "default",
                    "display_name": model_name.split('/')[-1]
                }
            }
        }
    
    # Add incognito mode defaults if not present
    if "incognito" not in config:
        config["incognito"] = {
            "enabled": True,
            "api": {
                "url": "http://localhost:11434/v1",
                "api_key": "ollama"
            },
            "model": {
                "name": "llama3.2:latest",
                "display_name": "Llama 3.2"
            }
        }
    
    # Ensure prompt config exists with valid defaults
    _ensure_prompt_config(config)
    
    return config

def _validate_required_fields(config: Dict[str, Any], console: Console, required_fields: List[str]) -> None:
    """Validate that all required configuration fields are present and valid"""
    for field_path in required_fields:
        field_keys = field_path.split('.')
        field_value = config
        
        # Navigate to the field value
        for key in field_keys:
            if key not in field_value:
                console.print(f"[red]Error: Missing required config field: {field_path}[/red]")
                sys.exit(1)
            field_value = field_value[key]
        
        # Check if value is valid
        if not field_value or field_value == "your_api_key_here":
            console.print(f"[red]Error: Please set a valid value for {field_path}[/red]")
            sys.exit(1)


def _validate_prompt_section(section: Dict[str, Any]) -> Dict[str, str]:
    """Validate and normalize a single prompt section dict."""
    if not isinstance(section, dict):
        return {"text": str(section), "fg": "", "bg": ""}
    return {
        "text": str(section.get("text", "")),
        "fg": str(section.get("fg", "")),
        "bg": str(section.get("bg", "")),
    }


def _ensure_prompt_config(config: Dict[str, Any]) -> None:
    """Ensure prompt config exists with valid defaults.
    
    Supports two config shapes:
      1) A single 'prompt.sections' list (used for all modes)
      2) Mode-specific overrides: 'prompt.ai', 'prompt.direct', 'prompt.incognito'
    
    Missing modes fall back to the built-in defaults from constants.py.
    """
    if "prompt" not in config:
        config["prompt"] = {}

    prompt_cfg = config["prompt"]

    # If user provided a flat 'sections' list, treat it as the 'ai' mode prompt
    # and replicate it to direct/incognito unless those already exist.
    if "sections" in prompt_cfg and not isinstance(prompt_cfg["sections"], dict):
        sections = [_validate_prompt_section(s) for s in prompt_cfg["sections"]]
        prompt_cfg.setdefault("ai", sections)
        prompt_cfg.setdefault("direct", sections)
        prompt_cfg.setdefault("incognito", sections)
    
    # Ensure each mode has a valid list of sections
    if "ai" not in prompt_cfg:
        prompt_cfg["ai"] = [dict(s) for s in DEFAULT_PROMPT_SECTIONS]
    else:
        prompt_cfg["ai"] = [_validate_prompt_section(s) for s in prompt_cfg["ai"]]

    if "direct" not in prompt_cfg:
        prompt_cfg["direct"] = [dict(s) for s in DEFAULT_PROMPT_SECTIONS_DIRECT]
    else:
        prompt_cfg["direct"] = [_validate_prompt_section(s) for s in prompt_cfg["direct"]]

    if "incognito" not in prompt_cfg:
        prompt_cfg["incognito"] = [dict(s) for s in DEFAULT_PROMPT_SECTIONS_INCOGNITO]
    else:
        prompt_cfg["incognito"] = [_validate_prompt_section(s) for s in prompt_cfg["incognito"]]
