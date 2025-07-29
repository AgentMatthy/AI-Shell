#!/usr/bin/env python

"""Constants and configuration values for AI Shell"""

from typing import List, Dict, Any
from pathlib import Path

# Application Information
APP_NAME = "AI Shell Assistant"
APP_VERSION = "1.0.0"

# File and Directory Constants
DEFAULT_CONFIG_FILE = "config.yaml"
DEFAULT_CONTEXT_FILE = "context.md"
HOME_DIR = Path.home()
APP_DATA_DIR = HOME_DIR / ".ai-shell"
LOGS_DIR = APP_DATA_DIR / "logs"
CONVERSATIONS_DIR = APP_DATA_DIR / "conversations"

# Default Configuration Values
DEFAULT_MAX_RETRIES = 30
DEFAULT_PAYLOAD_TRUNCATE_LENGTH = 1500
DEFAULT_AUTO_SAVE_INTERVAL = 5
DEFAULT_MAX_RECENT_CONVERSATIONS = 10

# Security Constants
DANGEROUS_COMMAND_PATTERNS = [
    'rm -rf /',
    'rm -rf *',
    'dd if=',
    'mkfs.',
    'fdisk',
    'wipefs',
    ':(){ :|: & };:',  # Fork bomb
    'chmod 000',
    'sudo rm -rf /',
    'sudo dd if=',
    'mkfs.ext4',
    'mkfs.ntfs',
    'format c:',
    '>dev/sda',
    '>dev/nvme',
    'shred -vfz',
]

# Directory changing commands
DIR_CHANGING_COMMANDS = ['cd', 'pushd', 'popd']

# Terminal Settings
TERMINAL_COLORS = {
    'user': 'green',
    'assistant': 'blue',
    'system': 'yellow',
    'error': 'red',
    'warning': 'yellow',
    'success': 'green',
    'info': 'cyan'
}

# Command Exit Codes
SUCCESS_EXIT_CODE = 0
ERROR_EXIT_CODE = 1

# Timeouts (in seconds)
COMMAND_TIMEOUT = 5
API_TIMEOUT = 30
PROCESS_CLEANUP_TIMEOUT = 2

# File Size Limits
MAX_CONFIG_FILE_SIZE = 1024 * 1024  # 1MB
MAX_CONTEXT_FILE_SIZE = 1024 * 100  # 100KB
MAX_LOG_FILE_SIZE = 1024 * 1024 * 10  # 10MB

# System Commands
SYSTEM_COMMANDS = [
    '/help', '/h', 'help',
    '/clear', '/new', '/reset', '/c', 'clear',
    '/exit', 'exit', 'quit', ';q', ':q', '/q',
    '/models', '/model', '/m',
    '/ai', '/dr', '/inc',
    '/save', '/load', '/conversations', '/cv',
    '/recent', '/r', '/archive', '/delete',
    '/status', '/p', '/payload'
]

# Default Incognito Configuration
DEFAULT_INCOGNITO_CONFIG = {
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

# Environment Variables
ENV_VARS = {
    'TERM': 'xterm-256color',
    'FORCE_COLOR': '1',
    'COLORTERM': 'truecolor'
}

# Logging Configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Rate Limiting
MAX_REQUESTS_PER_MINUTE = 60
MAX_COMMAND_LENGTH = 1000
MAX_RESPONSE_LENGTH = 10000

# Validation Patterns
SAFE_FILENAME_PATTERN = r'^[a-zA-Z0-9._-]+$'
API_KEY_PATTERN = r'^[a-zA-Z0-9\-_]{10,}$'