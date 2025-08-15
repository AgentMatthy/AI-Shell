# AI Shell Assistant

A Linux terminal assistant that uses AI to execute commands and answer questions through natural language.

## Demo

Check out AI Shell in action:

![Demo Video](.github/aishelldemo.mp4)

## Setup

1. Clone or download the project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create your `config.yaml` (See [Configuration](#configuration))
4. Configure your `context.md` file (See [Context](#context))
5. Run the assistant:
   ```bash
   python main.py
   ```

### Configuration

The `config.yaml` file contains all the configuration settings for the AI terminal assistant.

It needs to be in the same directory as the `main.py` file.

These are all the available settings and their default values: (Paste this into your `config.yaml` for a quick setup)

```yaml
# AI Shell Configuration File
# This file contains all the configuration settings for the AI terminal assistant

# API Configuration - PRECONFIGURED FOR OPENROUTER.AI
api:
  url: "https://openrouter.ai/api/v1"  # OpenRouter API endpoint
  api_key: ""  # Your API key

# Tavily Web Search Configuration
tavily:
  api_key: ""  # Your Tavily API key - get it from https://tavily.com/
  max_results: 3  # Maximum number of search results to return
  search_depth: "advanced"  # Search depth: "basic" or "advanced"
  include_answer: true  # Include AI-generated answer in search results
  include_raw_content: false  # Include raw content from web pages
  include_domains: []  # List of domains to include (empty = all domains)
  exclude_domains: []  # List of domains to exclude

# Models Configuration
models:
  # Primary model for generating responses and determining task completion
  response_model: gemini-2.5-pro
  
  # Available models with aliases for easy switching
  available:
    # Free models - no cost per request
    maverick:
      name: "meta-llama/llama-4-maverick:free"
      alias: "maverick"
      display_name: "Llama 4 Maverick"
    qwen:
      name: "qwen/qwen3-235b-a22b:free"
      alias: "qwen"
      display_name: "Qwen 3 235B"
    deepseek:
      name: "deepseek/deepseek-chat-v3-0324:free"
      alias: "deepseek"
      display_name: "DeepSeek V3"
    hermes:
      name: "nousresearch/deephermes-3-mistral-24b-preview:free"
      alias: "hermes"
      display_name: "DeepHermes 3"
    scout:
      name: "meta-llama/llama-4-scout:free"
      alias: "scout"
      display_name: "Llama 4 Scout"
    gemini:
      name: "google/gemini-2.0-flash-exp:free"
      alias: "gemini-2"
      display_name: "Gemini 2.0 Flash"
    
    # Paid models - higher quality but cost per request
    gemini-lite:
      name: "google/gemini-2.0-flash-lite-001"
      alias: "gemini-2-lite"
      display_name: "Gemini 2.0 Flash Lite"
    grok:
      name: "x-ai/grok-3-mini-beta"
      alias: "grok"
      display_name: "Grok 3 Mini"
    gemini-25:
      name: "google/gemini-2.5-flash-preview-05-20"
      alias: "gemini-2.5-flash"
      display_name: "Gemini 2.5 Flash"
    hermes-405b:
      name: "nousresearch/hermes-3-llama-3.1-405b"
      alias: "hermes-405b"
      display_name: "Hermes 3 405B"
    claude:
      name: "anthropic/claude-3.5-haiku"
      alias: "claude"
      display_name: "Claude 3.5 Haiku"
    claude-3:
      name: "anthropic/claude-3-haiku"
      alias: "claude-3"
      display_name: "Claude 3 Haiku"
    4o-mini:
      name: "openai/gpt-4o-mini"
      alias: "4o-mini"
      display_name: "GPT 4o Mini"
    4.1-nano:
      name: "openai/gpt-4.1-nano"
      alias: "4.1-nano"
      display_name: "GPT 4.1 Nano"
    command-r:
      name: "cohere/command-r-08-2024"
      alias: "command-r"
      display_name: "Command R"
    caller:
      name: "arcee-ai/caller-large"
      alias: "caller"
      display_name: "Caller Large"

    # Expensive models - Best quality but very expensive
    gemini-2.5-pro:
      name: "google/gemini-2.5-pro-preview"
      alias: "gemini-2.5-pro"
      display_name: "Gemini 2.5 Pro"
    command-r+:
      name: "cohere/command-r-plus-08-2024"
      alias: "command-r+"
      display_name: "Command R+"
    claude-4:
      name: "anthropic/claude-sonnet-4"
      alias: "claude-4"
      display_name: "Claude Sonnet 4"

# Shell Settings
settings:
  max_retries: 30  # Maximum number of retry attempts for failed commands
  payload_truncate_length: 1500  # Length to truncate long messages in payload display
  default_mode: ai
  show_welcome_message: false

# Conversation Management Settings
conversations:
  auto_save_interval: 5  # Auto-save every N interactions
  max_recent: 10  # Keep this many recent conversations
  resume_on_startup: true  # Ask to resume previous session on startup
  storage_path: "~/.ai-shell/conversations"  # Where to store conversation files

# Incognito Mode Configuration
incognito:
  enabled: true  # Enable/disable incognito mode functionality
  api:
    url: "http://localhost:11434/v1"  # Ollama API endpoint (local)
    api_key: "ollama"  # Ollama doesn't require a real API key
  model:
    name: "artifish/llama3.2-uncensored"  # Local model name in Ollama
    display_name: "Llama 3.2 Uncensored"  # Human-readable model name
```

### Context

The `context.md` file contains permanent additional instructions for the AI Shell Assistant.

It needs to be in the same directory as the `main.py` file.

It is recommended to add information like your linux distribution, your preferred package manager, or other info that you should take into account when running commands.

This is an example of a `context.md` file:

```markdown
- My linux distro is Manjaro
- My preferred package manager is pacman and yay
- When installing a package, please use the "overwrite='*'" flag, because my packages may be somewhat corrupted
```

## Usage

### Basic Commands

- **Natural requests**: "List all Python files" or "What's my disk usage?"
- **Questions**: "How do I install Docker?" or "What does this error mean: ... ?"
- **Direct commands**: Use `!` prefix like `!ls -la` to run commands directly or switch to direct mode with `/dr`

### System Commands

- `/help` - Show help (`/h`)
- `/models` - List available models (`/m`)
- `/model <name>` - Switch model
- `/clear` - Clear conversation (`/c`)
- `/save` - Save conversation
- `/load` - Load conversation
- `/inc` - Toggle incognito mode
- `/exit` - Exit

### Modes

- **AI Mode** (`/ai`): Natural language requests processed by AI
- **Direct Mode** (`/dr`): Commands executed directly without AI
- **Incognito Mode** (`/inc`): Uses local Ollama model, conversations not saved
