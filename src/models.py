#!/usr/bin/env python

from rich.console import Console
from rich.table import Table

class ModelManager:
    def __init__(self, config):
        self.config = config
        self.console = Console()
        self.current_model = config["models"]["response_model"]
    
    def get_model_display_name(self, model_alias):
        """Get human-readable display name for a model alias"""
        available_models = self.config["models"].get("available", {})
        if model_alias in available_models:
            return available_models[model_alias].get("display_name", model_alias)
        return model_alias
    
    def get_api_model_name(self, model_alias):
        """Get the actual API model name that should be sent to the API"""
        available_models = self.config["models"].get("available", {})
        if model_alias in available_models:
            return available_models[model_alias]["name"]
        return model_alias
    
    def list_models(self):
        """Display available models in a table"""
        table = Table(title="Available Models")
        table.add_column("Alias", style="cyan")
        table.add_column("Display Name", style="magenta")
        table.add_column("API Name", style="yellow")
        table.add_column("Current", style="green")
        
        if "available" in self.config["models"]:
            for alias, model_info in self.config["models"]["available"].items():
                current_marker = "✓" if alias == self.current_model else ""
                table.add_row(
                    alias,
                    model_info.get("display_name", alias),
                    model_info["name"],
                    current_marker
                )
        else:
            # Fallback for legacy config
            table.add_row("default", "Default Model", "N/A", "✓")
        
        self.console.print(table)
    
    def switch_model(self, new_model):
        """Switch to a different model"""
        if "available" in self.config["models"]:
            if new_model not in self.config["models"]["available"]:
                self.console.print(f"[red]Error: Model '{new_model}' not found in available models[/red]")
                return False
        
        self.current_model = new_model
        display_name = self.get_model_display_name(new_model)
        self.console.print(f"[green]Switched to model: {display_name}[/green]")
        return True
    
    def get_current_model_for_api(self):
        """Get the API model name for the current model"""
        return self.get_api_model_name(self.current_model)
    
    def get_task_checker_model_for_api(self):
        """Get the API model name for the task checker"""
        task_checker_model = self.config["models"]["task_checker_model"]
        return self.get_api_model_name(task_checker_model)
