# ChatDev Complete Tutorial: Build Software with AI Agents

Welcome to the comprehensive tutorial for ChatDev! This guide will help you get started, configure different AI models, and build amazing software with AI agents, regardless of where you are in the world.

## Table of Contents

1. [Introduction](#introduction)
2. [Quick Start](#quick-start)
3. [Installation Guide](#installation-guide)
4. [Model Configuration](#model-configuration)
5. [Running Your First Project](#running-your-first-project)
6. [Advanced Configuration](#advanced-configuration)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## Introduction

ChatDev is a virtual software company powered by multiple AI agents that collaborate to build software. Each agent has a specific role (CEO, CTO, Programmer, Reviewer, Tester, etc.) and works together through specialized phases to create complete software projects.

### What You Can Build

- Desktop applications (with GUI)
- Web applications
- Command-line tools
- Games
- Data processing scripts
- And much more!

---

## Quick Start

### Prerequisites

- **Python 3.9 or higher** (Python 3.10+ recommended)
- **An API key** from one of the supported AI providers:
  - OpenAI (GPT models)
  - Google (Gemini models)
  - DeepSeek
  - Or any OpenAI-compatible API endpoint

### 5-Minute Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/OpenBMB/ChatDev.git
   cd ChatDev
   ```

2. **Create a virtual environment:**
   ```bash
   # Using conda (recommended)
   conda create -n ChatDev python=3.9 -y
   conda activate ChatDev

   # Or using venv
   python3 -m venv ChatDev_env
   source ChatDev_env/bin/activate  # On Windows: ChatDev_env\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set your API key:**
   ```bash
   # For OpenAI (default)
   export OPENAI_API_KEY="your-api-key-here"

   # For other providers, see Model Configuration section below
   ```

5. **Run your first project:**
   ```bash
   python3 run.py --task "Create a simple calculator" --name "Calculator"
   ```

That's it! Your software will be generated in the `WareHouse/` directory.

---

## Installation Guide

### Step-by-Step Installation

#### 1. System Requirements

- **Operating System:** Windows, macOS, or Linux
- **Python:** 3.9 or higher
- **RAM:** At least 4GB (8GB+ recommended)
- **Disk Space:** At least 2GB free space
- **Internet Connection:** Required for API calls

#### 2. Python Installation

**Windows:**
- Download Python from [python.org](https://www.python.org/downloads/)
- During installation, check "Add Python to PATH"
- Verify installation: `python --version`

**macOS:**
- Python 3.9+ is usually pre-installed
- Verify: `python3 --version`
- If not installed, use Homebrew: `brew install python@3.9`

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.9 python3-pip python3-venv

# Fedora/CentOS
sudo dnf install python3.9 python3-pip
```

#### 3. Install ChatDev

```bash
# Clone the repository
git clone https://github.com/OpenBMB/ChatDev.git
cd ChatDev

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Verify Installation

```bash
python3 run.py --help
```

You should see the help message with all available options.

---

## Model Configuration

ChatDev supports multiple AI model providers. Choose the one that works best for you based on availability, cost, and performance in your region.

### Supported Models

| Provider | Models | API Key Variable | Base URL Variable |
|----------|--------|------------------|-------------------|
| **OpenAI** | GPT-3.5, GPT-4, GPT-4 Turbo, GPT-4o, GPT-4o-mini | `OPENAI_API_KEY` | `BASE_URL` (optional) |
| **Google Gemini** | gemini-pro, gemini-pro-vision | `GOOGLE_API_KEY` | - |
| **DeepSeek** | deepseek-chat, deepseek-coder | `DEEPSEEK_API_KEY` | `DEEPSEEK_BASE_URL` |
| **OpenAI-Compatible** | Any OpenAI-compatible API | `OPENAI_API_KEY` | `BASE_URL` |

### Configuration Methods

#### Method 1: Environment Variables (Recommended)

**For OpenAI:**
```bash
# Unix/Linux/macOS
export OPENAI_API_KEY="sk-your-key-here"
export BASE_URL="https://api.openai.com/v1"  # Optional, for custom endpoints

# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-your-key-here"
$env:BASE_URL="https://api.openai.com/v1"

# Windows (Command Prompt)
set OPENAI_API_KEY=sk-your-key-here
set BASE_URL=https://api.openai.com/v1
```

**For Google Gemini:**
```bash
# Unix/Linux/macOS
export GOOGLE_API_KEY="your-google-api-key"
export MODEL_PROVIDER="gemini"

# Windows
$env:GOOGLE_API_KEY="your-google-api-key"
$env:MODEL_PROVIDER="gemini"
```

**For DeepSeek:**
```bash
# Unix/Linux/macOS
export DEEPSEEK_API_KEY="your-deepseek-key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com/v1"
export MODEL_PROVIDER="deepseek"

# Windows
$env:DEEPSEEK_API_KEY="your-deepseek-key"
$env:DEEPSEEK_BASE_URL="https://api.deepseek.com/v1"
$env:MODEL_PROVIDER="deepseek"
```

#### Method 2: Using .env File (Alternative)

Create a `.env` file in the ChatDev root directory:

```bash
# .env file
OPENAI_API_KEY=sk-your-key-here
BASE_URL=https://api.openai.com/v1
MODEL_PROVIDER=openai
```

Then load it before running:
```bash
# Unix/Linux/macOS
export $(cat .env | xargs)

# Or use python-dotenv (install: pip install python-dotenv)
```

#### Method 3: Command Line Arguments

```bash
python3 run.py \
  --task "Your task description" \
  --name "ProjectName" \
  --model "GPT_4" \
  --config "Default"
```

### Model Selection Guide

#### OpenAI Models

| Model | Best For | Cost | Speed |
|-------|----------|------|-------|
| `GPT_3_5_TURBO` | Simple projects, testing | Low | Fast |
| `GPT_4` | Complex projects, high quality | High | Medium |
| `GPT_4_TURBO` | Large projects, best quality | Very High | Medium |
| `GPT_4O` | Latest features, balanced | High | Fast |
| `GPT_4O_MINI` | Cost-effective, good quality | Low | Very Fast |

**Usage:**
```bash
python3 run.py --task "Build a web app" --name "WebApp" --model "GPT_4O"
```

#### Google Gemini Models

**Setup:**
1. Get API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Set environment variables:
   ```bash
   export GOOGLE_API_KEY="your-key"
   export MODEL_PROVIDER="gemini"
   ```
3. Use model name: `GEMINI_PRO` or `GEMINI_PRO_VISION`

**Usage:**
```bash
python3 run.py --task "Build a game" --name "Game" --model "GEMINI_PRO"
```

#### DeepSeek Models

**Setup:**
1. Get API key from [DeepSeek Platform](https://platform.deepseek.com/)
2. Set environment variables:
   ```bash
   export DEEPSEEK_API_KEY="your-key"
   export DEEPSEEK_BASE_URL="https://api.deepseek.com/v1"
   export MODEL_PROVIDER="deepseek"
   ```
3. Use model name: `DEEPSEEK_CHAT` or `DEEPSEEK_CODER`

**Usage:**
```bash
python3 run.py --task "Build a CLI tool" --name "CLITool" --model "DEEPSEEK_CHAT"
```

#### Using OpenAI-Compatible APIs

Many providers offer OpenAI-compatible APIs. To use them:

```bash
export OPENAI_API_KEY="your-provider-key"
export BASE_URL="https://api.your-provider.com/v1"
export MODEL_PROVIDER="openai"  # Use OpenAI provider with custom base URL
```

Examples:
- **Anthropic Claude** (via proxy)
- **Local models** (via Ollama, vLLM, etc.)
- **Regional providers** (for better latency)

---

## Running Your First Project

### Basic Command

```bash
python3 run.py --task "Your project description" --name "ProjectName"
```

### Command Options

```bash
python3 run.py \
  --task "Create a todo list application with GUI" \
  --name "TodoApp" \
  --org "MyCompany" \
  --model "GPT_4O" \
  --config "Default"
```

**Parameters:**
- `--task`: Description of what you want to build (required)
- `--name`: Name of your project (required)
- `--org`: Organization name (default: "DefaultOrganization")
- `--model`: AI model to use (default: "GPT_3_5_TURBO")
- `--config`: Configuration preset (default: "Default")
- `--path`: Path to existing code for incremental development (optional)

### Example Projects

**1. Simple Calculator:**
```bash
python3 run.py --task "Create a calculator with GUI that can do basic math operations" --name "Calculator"
```

**2. Todo List App:**
```bash
python3 run.py --task "Build a todo list application with add, delete, and mark complete features" --name "TodoList"
```

**3. Game:**
```bash
python3 run.py --task "Create a simple snake game with score tracking" --name "SnakeGame"
```

**4. Web Scraper:**
```bash
python3 run.py --task "Build a web scraper that extracts article titles from a news website" --name "NewsScraper"
```

### Finding Your Generated Software

After running, your software will be in:
```
WareHouse/ProjectName_OrganizationName_Timestamp/
```

Example:
```
WareHouse/Calculator_DefaultOrganization_20240101120000/
├── main.py
├── requirements.txt
├── manual.md
└── ...
```

### Running Generated Software

```bash
cd WareHouse/ProjectName_OrganizationName_Timestamp
pip install -r requirements.txt
python3 main.py
```

---

## Advanced Configuration

### Custom Company Configuration

Create your own configuration in `CompanyConfig/YourConfig/`:

```bash
mkdir -p CompanyConfig/MyConfig
cp CompanyConfig/Default/* CompanyConfig/MyConfig/
```

Then edit the JSON files:
- `ChatChainConfig.json`: Development workflow
- `PhaseConfig.json`: Phase configurations
- `RoleConfig.json`: Agent role definitions

Use your config:
```bash
python3 run.py --task "Your task" --name "Project" --config "MyConfig"
```

### Available Configurations

- **Default**: Standard software development workflow
- **Art**: Includes image generation capabilities
- **Human**: Allows human interaction during code review
- **Incremental**: Build upon existing code

### Incremental Development

Build upon existing code:

```bash
python3 run.py \
  --task "Add user authentication to the existing app" \
  --name "MyApp" \
  --path "/path/to/existing/code"
```

### Git Integration

Enable Git version control in `CompanyConfig/Default/ChatChainConfig.json`:

```json
{
  "git_management": "True"
}
```

### Memory/Experience Pool

Enable experience-based learning:

1. Set in `ChatChainConfig.json`:
   ```json
   {
     "with_memory": "True"
   }
   ```

2. Prepare memory file at `ecl/memory/MemoryCards.json`

---

## Troubleshooting

### Common Issues

#### 1. API Key Not Found

**Error:** `KeyError: 'OPENAI_API_KEY'`

**Solution:**
```bash
# Verify your API key is set
echo $OPENAI_API_KEY  # Unix/Linux/macOS
echo %OPENAI_API_KEY%  # Windows

# Set it if missing
export OPENAI_API_KEY="your-key-here"
```

#### 2. Module Not Found

**Error:** `ModuleNotFoundError: No module named 'xxx'`

**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Or install specific missing package
pip install package-name
```

#### 3. Model Not Supported

**Error:** `ValueError: Unknown model`

**Solution:**
- Check available models: `python3 run.py --help`
- Use supported model names (see Model Configuration section)
- For new providers, check if model backend is implemented

#### 4. Rate Limit Errors

**Error:** `Rate limit exceeded` or `429 Too Many Requests`

**Solution:**
- Use a model with higher rate limits (e.g., GPT-3.5-turbo)
- Add delays between requests
- Upgrade your API plan
- Use a different provider

#### 5. Connection Timeout

**Error:** `Connection timeout` or network errors

**Solution:**
- Check internet connection
- Use a provider with servers closer to your region
- Set custom BASE_URL for regional endpoints
- Increase timeout settings

#### 6. Out of Memory

**Error:** `Out of memory` or system crashes

**Solution:**
- Use smaller models (GPT-3.5 instead of GPT-4)
- Reduce `max_turn_step` in configuration
- Close other applications
- Use cloud-based execution

### Getting Help

1. **Check Logs:** Look in `WareHouse/ProjectName_*/timestamp.log`
2. **GitHub Issues:** [Open an issue](https://github.com/OpenBMB/ChatDev/issues)
3. **Discord:** Join the [Discord community](https://discord.gg/bn4t2Jy6TT)
4. **Documentation:** Check [Wiki](wiki.md) for detailed guides

---

## Best Practices

### 1. Task Description Tips

**Good:**
- "Create a calculator with GUI that supports addition, subtraction, multiplication, and division"
- "Build a todo list app with add, delete, edit, and mark complete features"
- "Develop a simple web scraper that extracts product names and prices from an e-commerce site"

**Avoid:**
- "Make an app" (too vague)
- "Build something cool" (no specific requirements)
- Extremely complex multi-feature requests in one go

### 2. Model Selection

- **Start with GPT-3.5-turbo** for testing and simple projects
- **Use GPT-4 or GPT-4o** for complex projects requiring high quality
- **Try Gemini or DeepSeek** if OpenAI is unavailable in your region
- **Use GPT-4o-mini** for cost-effective development

### 3. Project Organization

- Use descriptive project names
- Set meaningful organization names
- Keep track of generated projects in `WareHouse/`
- Use Git integration for version control

### 4. Cost Management

- Monitor API usage and costs
- Use cheaper models for testing
- Set up usage alerts with your API provider
- Consider using local models for development

### 5. Iterative Development

- Start with simple features
- Use incremental mode to add features gradually
- Test generated code before adding complexity
- Use Human mode for manual review

### 6. Regional Considerations

- **China/Asia:** Consider DeepSeek or regional OpenAI proxies
- **Europe:** OpenAI or local providers
- **Americas:** OpenAI, Anthropic, or Google
- **Other regions:** Check provider availability and latency

---

## Next Steps

1. **Explore Examples:** Check `WareHouse/` for example projects
2. **Customize Workflows:** Create your own company configurations
3. **Join Community:** Share your projects and get help
4. **Read Wiki:** Deep dive into [advanced features](wiki.md)
5. **Contribute:** Help improve ChatDev for everyone

---

## Quick Reference

### Essential Commands

```bash
# Basic usage
python3 run.py --task "description" --name "ProjectName"

# With specific model
python3 run.py --task "description" --name "Project" --model "GPT_4O"

# With custom config
python3 run.py --task "description" --name "Project" --config "Art"

# Incremental development
python3 run.py --task "add feature" --name "Project" --path "/existing/code"
```

### Environment Variables

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."
export BASE_URL="https://api.openai.com/v1"  # Optional

# Google Gemini
export GOOGLE_API_KEY="..."
export MODEL_PROVIDER="gemini"

# DeepSeek
export DEEPSEEK_API_KEY="..."
export DEEPSEEK_BASE_URL="https://api.deepseek.com/v1"
export MODEL_PROVIDER="deepseek"
```

### File Locations

- **Generated Software:** `WareHouse/ProjectName_Org_Timestamp/`
- **Configurations:** `CompanyConfig/ConfigName/`
- **Logs:** `WareHouse/ProjectName_Org_Timestamp/timestamp.log`
- **Memory/Experience:** `ecl/memory/MemoryCards.json`

---

## Support and Resources

- **Documentation:** [Wiki](wiki.md)
- **GitHub:** [Repository](https://github.com/OpenBMB/ChatDev)
- **Discord:** [Community](https://discord.gg/bn4t2Jy6TT)
- **Issues:** [GitHub Issues](https://github.com/OpenBMB/ChatDev/issues)
- **Email:** qianc62@gmail.com

---

**Happy Coding with ChatDev! 🚀**

*Last Updated: 2024*

