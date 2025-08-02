#!/usr/bin/env python

import os
import sys
import yaml
from typing import Dict, Any, List, Optional
from rich.console import Console

def load_config(config_path: str = "config.yaml") -> Optional[Dict[str, Any]]:
    """Load and validate configuration from YAML file"""
    console = Console()
    
    if not os.path.exists(config_path):
        console.print(f"[red]Error: Config file '{config_path}' not found![/red]")
        console.print(f"[yellow]Please create a config.yaml file with your API settings.[/yellow]")
        sys.exit(1)
    
    # Check if file is readable
    if not os.access(config_path, os.R_OK):
        console.print(f"[red]Error: Config file '{config_path}' is not readable![/red]")
        sys.exit(1)
    
    # Check file size (prevent loading massive files)
    try:
        file_size = os.path.getsize(config_path)
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
