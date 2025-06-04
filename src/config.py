#!/usr/bin/env python

import os
import sys
import yaml
from rich.console import Console

def load_config(config_path="config.yaml"):
    """Load configuration from YAML file"""
    console = Console()
    
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
