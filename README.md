# AI Shell Assistant

A sophisticated command-line AI assistant that provides intelligent terminal interaction through natural language processing. This tool enables users to execute commands, get explanations, and receive AI-powered assistance directly from their terminal environment.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Commands and Controls](#commands-and-controls)
- [Conversation Management](#conversation-management)
- [Web Search Integration](#web-search-integration)
- [Model Management](#model-management)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Overview

AI Shell Assistant is an agentic AI tool designed to interact with Linux terminals through OpenAI-compatible APIs. It serves as an intelligent intermediary between users and their command-line environment, capable of executing commands, providing explanations, and maintaining conversational context across sessions.

The application is built with a modular architecture, separating concerns into distinct components for configuration management, user interface, conversation handling, model management, and command execution.

## Features

### Core Functionality
- **Natural Language Command Execution**: Translate natural language requests into terminal commands
- **Intelligent Response Generation**: AI-powered explanations and guidance
- **Persistent Conversation History**: Save and resume conversations across sessions
- **Multi-Model Support**: Switch between different AI models for responses and task checking
- **Command Confirmation**: Optional confirmation prompts before executing potentially dangerous commands
- **Task Status Monitoring**: Automatic verification of command execution success

### Advanced Features
- **Web Search Integration**: Tavily-powered web search capabilities for enhanced information retrieval
- **Session Management**: Auto-save functionality with conversation archiving
- **Directory Synchronization**: Maintains shell state consistency across command executions
- **Rich Terminal UI**: Enhanced visual feedback using Rich library formatting
- **Input History**: Command history with intelligent auto-completion
- **Flexible Configuration**: YAML-based configuration with validation and legacy format support

## Architecture

The application follows a modular design pattern with the following components:

### Core Components

```
src/
├── app.py              # Main application controller
├── ui.py               # User interface management
├── config.py           # Configuration loading and validation
├── chat.py             # AI chat response generation
├── models.py           # Model management and switching
├── commands.py         # Command execution and shell management
├── conversation_manager.py  # Session persistence and management
├── input_handler.py    # User input processing
├── terminal_input.py   # Terminal input interface
└── web_search.py       # Web search functionality
```

### Component Responsibilities

**AIShellApp** (`app.py`)
- Main application orchestration
- User input processing loop
- Response handling and command execution
- Session state management

**UIManager** (`ui.py`)
- Terminal output formatting
- User prompts and confirmations
- Status messages and error display
- Rich library integration for enhanced visuals

**ConversationManager** (`conversation_manager.py`)
- Session persistence and auto-save
- Conversation archiving and loading
- Recent conversation tracking
- Session metadata management

**ChatManager** (`chat.py`)
- AI response generation
- System prompt management
- Task status verification
- Response processing and validation

**ModelManager** (`models.py`)
- Model configuration and switching
- API model name mapping
- Model availability validation

**WebSearchManager** (`web_search.py`)
- Tavily API integration
- Search result formatting
- Configuration-based search parameters

## Installation

### Prerequisites

- Python 3.8 or higher
- OpenAI-compatible API access (OpenAI, Anthropic, local models, etc.)
- Linux or macOS environment (Windows support may vary)

### Steps

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd AI-Shell
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create configuration file**:
   ```bash
   cp config.yaml.example config.yaml
   ```

4. **Configure your API settings** (see [Configuration](#configuration) section)

5. **Run the application**:
   ```bash
   python main.py
   ```

### Dependencies

The application requires the following Python packages:

```
openai>=1.0.0
pyyaml>=6.0
rich>=13.0.0
prompt-toolkit>=3.0.0
tavily-python>=0.3.0  # Optional: for web search functionality
```

## Configuration

### Configuration File Structure

The application uses a YAML configuration file (`config.yaml`) with the following structure:

```yaml
# API Configuration
api:
  url: "https://api.openai.com/v1"  # API endpoint URL
  api_key: "your_api_key_here"      # Your API key

# Model Configuration
models:
  response_model: "gpt-4"           # Primary model for responses
  task_checker_model: "gpt-3.5-turbo"  # Model for task verification
  available_models:                 # Available models for switching
    gpt4: "gpt-4"
    gpt35: "gpt-3.5-turbo"
    claude: "claude-3-sonnet-20240229"

# Application Settings
settings:
  max_history: 50                   # Maximum conversation history length
  auto_save: true                   # Enable automatic conversation saving
  confirm_commands: true            # Require confirmation for commands
  show_directory: true              # Show current directory in prompts

# Conversation Management
conversation:
  save_directory: "conversations"   # Directory for saved conversations
  recent_limit: 10                  # Number of recent conversations to track
  auto_archive_days: 30            # Days before auto-archiving conversations

# Web Search (Optional)
tavily:
  api_key: "your_tavily_api_key_here"  # Tavily API key for web search
  max_results: 5                    # Maximum search results
  search_depth: "basic"             # Search depth (basic/advanced)
  include_answer: true              # Include direct answer in results
  include_raw_content: false        # Include raw webpage content
```

### Configuration Validation

The application automatically validates configuration files and provides helpful error messages for:
- Missing required fields
- Invalid API configurations
- Malformed YAML syntax
- Legacy configuration format conversion

### Legacy Configuration Support

The application supports legacy configuration formats and automatically converts them to the modern dual-model format. Legacy configurations using a single `default` model will be automatically upgraded.

## Usage

### Basic Usage

1. **Start the application**:
   ```bash
   python main.py
   ```

2. **Interact with the AI**:
   ```
   You: How do I list all files in the current directory?
   AI Assistant: To list all files in the current directory, you can use the `ls` command...
   ```

3. **Execute commands with confirmation**:
   ```
   You: Delete all .tmp files
   AI Assistant: I'll help you delete all .tmp files. Here's the command:
   
   find . -name "*.tmp" -type f -delete
   
   Execute this command? [Y/n]: y
   ```

### Session Management

The application automatically saves conversation state and can resume previous sessions:

```
Found previous session from 2024-01-15 14:30:25
Session: Working on Python script optimization (15 messages)
Resume this session? [Y/n]: y
```

### Advanced Usage Patterns

**Multi-step task execution**:
```
You: Set up a Python virtual environment and install requirements
AI Assistant: I'll help you set up a Python virtual environment and install requirements. Let me break this down into steps:

1. Create virtual environment
2. Activate virtual environment  
3. Install requirements

Let's start:
```

**Context-aware assistance**:
```
You: The previous command failed
AI Assistant: I see the command failed with exit code 1. Let me analyze the error output and suggest a solution...
```

## Commands and Controls

### Conversation Commands

- `/help` - Display help information
- `/status` - Show current session status
- `/save [name]` - Save current conversation
- `/load [name]` - Load a saved conversation
- `/list` - List all saved conversations
- `/recent` - Show recent conversations
- `/clear` - Clear current conversation
- `/archive` - Archive current conversation
- `/exit` - Save and exit application

### Model Commands

- `/models` - List available models
- `/model <alias>` - Switch to specified model
- `/payload` - Show current conversation payload

### Special Controls

- **Ctrl+C**: Interrupt current operation
- **Ctrl+D**: Exit application
- **Tab**: Auto-complete commands and paths
- **Up/Down arrows**: Navigate command history

## Conversation Management

### Automatic Session Handling

The application provides sophisticated session management:

**Auto-save**: Conversations are automatically saved at regular intervals and when switching contexts.

**Session Resume**: The application detects incomplete sessions and offers to resume them on startup.

**Conversation Archiving**: Old conversations are automatically archived to prevent clutter.

### Manual Session Control

**Save Conversations**:
```bash
/save project_setup
# Saves current conversation with name "project_setup"
```

**Load Conversations**:
```bash
/load project_setup
# Loads the "project_setup" conversation
```

**List Recent Conversations**:
```bash
/recent
# Shows numbered list of recent conversations
# Use /load 1, /load 2, etc. to load by number
```

### Session File Structure

Conversations are stored in JSON format with metadata:

```json
{
  "session_id": "unique_session_identifier",
  "created": "2024-01-15T14:30:25Z",
  "updated": "2024-01-15T15:45:30Z",
  "summary": "Working on Python script optimization",
  "message_count": 15,
  "messages": [...],
  "metadata": {
    "model": "gpt-4",
    "directory": "/home/user/project"
  }
}
```

## Web Search Integration

### Tavily Configuration

To enable web search functionality:

1. **Install Tavily package**:
   ```bash
   pip install tavily-python
   ```

2. **Get Tavily API key** from [Tavily](https://tavily.com)

3. **Configure in config.yaml**:
   ```yaml
   tavily:
     api_key: "your_tavily_api_key_here"
     max_results: 5
     search_depth: "basic"
   ```

### Search Usage

Web search is automatically triggered when the AI determines external information is needed:

```
You: What's the latest version of Python?
AI Assistant: Let me search for the latest Python version information...

[Performs web search]

Based on current information, Python 3.12.1 is the latest stable release...
```

### Search Configuration Options

- `max_results`: Maximum number of search results (default: 5)
- `search_depth`: Search depth - "basic" or "advanced" (default: "basic")
- `include_answer`: Include direct answer in results (default: true)
- `include_raw_content`: Include raw webpage content (default: false)
- `include_domains`: List of domains to include in search
- `exclude_domains`: List of domains to exclude from search

## Model Management

### Supported Model Types

The application supports any OpenAI-compatible API:

**Cloud Providers**:
- OpenAI (GPT-3.5, GPT-4, GPT-4 Turbo)
- Anthropic Claude (via compatible APIs)
- Google Gemini (via compatible APIs)

**Local Models**:
- Ollama
- LM Studio
- LocalAI
- Any OpenAI-compatible local server

### Model Configuration

Configure multiple models for different purposes:

```yaml
models:
  response_model: "gpt-4"           # Primary conversational model
  task_checker_model: "gpt-3.5-turbo"  # Lightweight model for task verification
  available_models:
    gpt4: "gpt-4"
    gpt35: "gpt-3.5-turbo"
    claude: "claude-3-sonnet-20240229"
    local: "llama2:7b"              # Local Ollama model
```

### Runtime Model Switching

Switch models during conversation:

```
You: /models
Available models:
- gpt4: gpt-4 (current)
- gpt35: gpt-3.5-turbo
- claude: claude-3-sonnet-20240229

You: /model claude
Switched to model: claude-3-sonnet-20240229
```

## Development

### Project Structure

```
AI-Shell/
├── main.py                 # Application entry point
├── config.yaml            # Configuration file
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── src/                   # Source code directory
│   ├── __init__.py
│   ├── app.py             # Main application class
│   ├── ui.py              # User interface management
│   ├── config.py          # Configuration handling
│   ├── chat.py            # AI chat management
│   ├── models.py          # Model management
│   ├── commands.py        # Command execution
│   ├── conversation_manager.py  # Session management
│   ├── input_handler.py   # Input processing
│   ├── terminal_input.py  # Terminal interface
│   └── web_search.py      # Web search functionality
└── conversations/         # Saved conversations directory
```

### Adding New Features

The modular architecture makes it easy to extend functionality:

**Adding New Commands**:
1. Extend the command parsing in `input_handler.py`
2. Implement command logic in appropriate manager class
3. Update help documentation

**Adding New Model Providers**:
1. Extend model configuration in `models.py`
2. Add provider-specific handling if needed
3. Update configuration validation

**Adding New UI Components**:
1. Extend `UIManager` class in `ui.py`
2. Use Rich library for consistent formatting
3. Maintain accessibility standards

### Testing

The application includes comprehensive error handling and logging:

**Debug Mode**: Set environment variable `DEBUG=1` for verbose logging

**Configuration Testing**: Use `--test-config` flag to validate configuration

**Model Testing**: Use `/status` command to verify model connectivity

## Troubleshooting

### Common Issues

**Configuration Errors**:
```
Error: Config file 'config.yaml' not found!
Solution: Copy config.yaml.example to config.yaml and configure your API settings
```

**API Connection Issues**:
```
Error: Failed to connect to API endpoint
Solution: Verify your API URL and key in config.yaml
```

**Model Not Available**:
```
Error: Model 'gpt-4' not available
Solution: Check your API plan and model availability
```

**Permission Denied**:
```
Error: Permission denied when saving conversation
Solution: Check write permissions in conversations directory
```

### Debug Information

Use the `/status` command to get comprehensive debug information:

```
You: /status
Current Status:
- Model: gpt-4 (response), gpt-3.5-turbo (task checker)
- Session: active (15 messages)
- Directory: /home/user/project
- Web Search: enabled (Tavily)
- Auto-save: enabled
- Last save: 2 minutes ago
```

### Log Files

The application logs important events and errors:
- Configuration validation results
- API connection status
- Command execution results
- Session save/load operations

### Getting Help

For additional support:
1. Check the `/help` command for built-in assistance
2. Review configuration file comments
3. Verify API provider documentation
4. Check Python package versions and compatibility

## Contributing

### Development Guidelines

1. **Code Style**: Follow PEP 8 Python style guidelines
2. **Documentation**: Update docstrings and comments for new functionality
3. **Error Handling**: Implement comprehensive error handling with user-friendly messages
4. **Testing**: Test new features with various model providers and configurations
5. **Backwards Compatibility**: Maintain compatibility with existing configuration files

### Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Implement changes with appropriate documentation
4. Test thoroughly with different configurations
5. Submit a pull request with detailed description

### Architecture Decisions

The application prioritizes:
- **Modularity**: Clear separation of concerns
- **Extensibility**: Easy addition of new features
- **User Experience**: Intuitive interface and helpful error messages
- **Reliability**: Robust error handling and session management
- **Performance**: Efficient command execution and response generation

This architecture enables the AI Shell Assistant to serve as a powerful and flexible tool for AI-enhanced terminal interaction while maintaining simplicity and reliability.

