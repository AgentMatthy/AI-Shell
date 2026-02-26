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
CONFIG_DIR = HOME_DIR / ".config" / "ai-shell"
APP_DATA_DIR = HOME_DIR / ".ai-shell"
LOGS_DIR = APP_DATA_DIR / "logs"
CONVERSATIONS_DIR = APP_DATA_DIR / "conversations"

# Full paths to config files
CONFIG_FILE_PATH = CONFIG_DIR / DEFAULT_CONFIG_FILE
CONTEXT_FILE_PATH = CONFIG_DIR / DEFAULT_CONTEXT_FILE

# Default Configuration Values
DEFAULT_MAX_RETRIES = 30
DEFAULT_PAYLOAD_TRUNCATE_LENGTH = 1500
DEFAULT_AUTO_SAVE_INTERVAL = 5
DEFAULT_MAX_RECENT_CONVERSATIONS = 10
DEFAULT_LONG_OUTPUT_THRESHOLD = 3000  # Character threshold for asking about truncation (legacy)

# Auto-truncation settings (context management)
DEFAULT_AUTO_TRUNCATE_THRESHOLD = 10000  # Character threshold for automatic truncation
DEFAULT_TRUNCATE_HEAD_LINES = 50         # Lines to keep from the start
DEFAULT_TRUNCATE_TAIL_LINES = 50         # Lines to keep from the end

# Security Constants (kept for backward compatibility)
DANGEROUS_COMMAND_PATTERNS = []

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
    '/status', '/p', '/payload', '/compact', '/resetconfig'
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
MAX_RESPONSE_LENGTH = 10000

# Validation Patterns
SAFE_FILENAME_PATTERN = r'^[a-zA-Z0-9._-]+$'
API_KEY_PATTERN = r'^[a-zA-Z0-9\-_]{10,}$'

# Default safe commands — read-only commands that can be auto-executed without confirmation.
# These commands cannot modify files, system state, or cause side effects regardless of arguments.
# Commands like sed, awk, find are excluded because they CAN be destructive with certain flags.
# Users can override this list in config.yaml under settings.safe_commands
DEFAULT_SAFE_COMMANDS = [
    # File/directory listing and info
    'ls', 'dir', 'tree', 'file', 'stat', 'readlink',
    # File content reading (truly read-only)
    'cat', 'head', 'tail', 'less', 'more', 'bat', 'batcat',
    # Text searching (read-only)
    'grep', 'egrep', 'fgrep', 'rg', 'ag', 'ack',
    # Text processing (read-only — cannot modify files)
    'wc', 'sort', 'uniq', 'cut', 'tr', 'rev', 'tac', 'fold', 'column',
    'nl', 'expand', 'unexpand', 'fmt', 'paste', 'join',
    # Comparison
    'diff', 'comm', 'cmp',
    # Checksums
    'md5sum', 'sha256sum', 'sha1sum', 'sha512sum', 'cksum', 'b2sum',
    # Binary inspection
    'xxd', 'od', 'hexdump', 'strings',
    # Command/path lookup
    'which', 'whereis', 'whatis', 'type', 'command',
    # System info
    'uname', 'hostname', 'uptime', 'date', 'cal',
    'whoami', 'id', 'groups', 'who', 'w', 'last',
    'df', 'du', 'free', 'ps', 'pgrep', 'pidof',
    'lsblk', 'lscpu', 'lsmem', 'lsusb', 'lspci', 'lsmod', 'lsof',
    'ip', 'ifconfig', 'ss', 'netstat', 'route',
    'env', 'printenv',
    'nproc', 'getconf', 'arch',
    # Path/directory utilities
    'pwd', 'realpath', 'dirname', 'basename',
    # Output (safe by itself — redirections are checked separately)
    'echo', 'printf',
    # Version/help
    'man', 'info', 'help',
    # Conditionals (read-only)
    'true', 'false', 'test', '[',
    # JSON/YAML processing (read-only)
    'jq', 'yq',
]

# Default Prompt Configuration
# Each section has: text (with $variables), fg (text color), bg (background color)
# Available variables: $model, $dir, $mode, $user, $host
DEFAULT_PROMPT_SECTIONS = [
    {"text": "AI Shell ", "fg": "#0066cc", "bg": ""},
    {"text": "[$mode - $model] ", "fg": "#0066cc", "bg": ""},
    {"text": "$dir", "fg": "#666666", "bg": ""},
    {"text": " > ", "fg": "#0066cc", "bg": ""},
]

# Mode-specific default prompt overrides (optional, keyed by mode name)
# If a mode key exists here, its sections replace DEFAULT_PROMPT_SECTIONS for that mode
DEFAULT_PROMPT_SECTIONS_DIRECT = [
    {"text": "AI Shell ", "fg": "#00cc66", "bg": ""},
    {"text": "[Direct] ", "fg": "#00cc66", "bg": ""},
    {"text": "$dir", "fg": "#666666", "bg": ""},
    {"text": " > ", "fg": "#00cc66", "bg": ""},
]

DEFAULT_PROMPT_SECTIONS_INCOGNITO = [
    {"text": "AI Shell ", "fg": "#8b3fbb", "bg": ""},
    {"text": "[Incognito - $model] ", "fg": "#8b3fbb", "bg": ""},
    {"text": "$dir", "fg": "#666666", "bg": ""},
    {"text": " > ", "fg": "#8b3fbb", "bg": ""},
]