#!/usr/bin/env python

import logging
import os
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler


class AIShellLogger:
    """Centralized logging system for AI Shell"""
    
    _instance: Optional['AIShellLogger'] = None
    
    def __new__(cls) -> 'AIShellLogger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.console = Console()
        self.logger = logging.getLogger("ai-shell")
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        # Create logs directory
        log_dir = Path.home() / ".ai-shell" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup file handler
        log_file = log_dir / "ai-shell.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Setup console handler with Rich
        console_handler = RichHandler(
            console=self.console,
            show_time=False,
            show_path=False,
            markup=True
        )
        console_handler.setLevel(logging.WARNING)  # Only show warnings/errors in console
        
        # Setup formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Configure logger
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.logger.critical(message, **kwargs)
    
    def log_command_execution(self, command: str, success: bool, output: str):
        """Log command execution details"""
        status = "SUCCESS" if success else "FAILED"
        self.info(f"Command {status}: {command}")
        if not success:
            self.debug(f"Command output: {output}")
    
    def log_api_request(self, model: str, prompt_length: int, response_length: int):
        """Log API request details"""
        self.debug(f"API Request - Model: {model}, Prompt: {prompt_length} chars, Response: {response_length} chars")
    
    def log_security_event(self, event_type: str, details: str):
        """Log security-related events"""
        self.warning(f"SECURITY EVENT - {event_type}: {details}")


# Global logger instance
logger = AIShellLogger()