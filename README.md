# AI Shell Assistant

A Linux terminal assistant that uses AI to execute commands and answer questions through natural language.

## Installation

1. Clone or download the project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your API key in `config.yaml`
4. Run the assistant:
   ```bash
   python main.py
   ```

## Configuration



## Usage

### Basic Commands

- **Natural requests**: "List all Python files" or "What's my disk usage?"
- **Questions**: "How do I install Docker?" or "What does this error mean?"
- **Direct commands**: Use `!` prefix like `!ls -la` to run commands directly

### System Commands

- `/help` - Show help
- `/models` - List available models
- `/model <name>` - Switch model
- `/clear` - Clear conversation
- `/save` - Save conversation
- `/load` - Load conversation
- `/inc` - Toggle incognito mode
- `/exit` - Exit

### Modes

- **AI Mode** (default): Natural language requests processed by AI
- **Direct Mode** (`/dr`): Commands executed directly without AI
- **Incognito Mode** (`/inc`): Uses local Ollama model, conversations not saved

## Features

- Interactive command execution with real terminal output
- Conversation history and persistence
- Multiple AI model support
- Web search integration (optional)
- Local model support via Ollama
- Tab completion and command history

## Requirements

- Python 3.7+
- Linux terminal
- Internet connection for AI models
- Optional: [Ollama](https://ollama.ai/) for local models

