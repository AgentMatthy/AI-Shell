#!/usr/bin/env python

import os
import sys
import yaml
from rich.console import Console

def load_config(config_path="config.yaml"):
    """Load and validate configuration from YAML file"""
    console = Console()
    
    if not os.path.exists(config_path):
        console.print(f"[red]Error: Config file '{config_path}' not found![/red]")
        console.print(f"[yellow]Please create a config.yaml file with your API settings.[/yellow]")
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

def _validate_and_normalize_config(config, console):
    """Validate and normalize configuration, converting legacy formats"""
    
    # Handle different config formats and convert to modern dual-model format
    if "models" in config:
        if "response_model" in config["models"] and "task_checker_model" in config["models"]:
            # Modern dual-model format - validate required fields
            _validate_required_fields(config, console, [
                "api.url", "api.api_key", 
                "models.response_model", "models.task_checker_model"
            ])
        elif "default" in config["models"]:
            # Legacy multi-model format - convert to dual-model
            _validate_required_fields(config, console, [
                "api.url", "api.api_key", "models.default"
            ])
            
            default_model = config["models"]["default"]
            config["models"]["response_model"] = default_model
            config["models"]["task_checker_model"] = default_model
        else:
            console.print(f"[red]Error: Invalid models configuration format[/red]")
            sys.exit(1)
    else:
        # Legacy single model format - convert to dual-model
        _validate_required_fields(config, console, [
            "api.url", "api.api_key", "api.model"
        ])
        
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

def _validate_required_fields(config, console, required_fields):
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
