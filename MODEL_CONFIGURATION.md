# Model Configuration Guide

This guide provides detailed instructions for configuring different AI model providers in ChatDev.

## Table of Contents

1. [OpenAI Models](#openai-models)
2. [Google Gemini Models](#google-gemini-models)
3. [DeepSeek Models](#deepseek-models)
4. [OpenAI-Compatible APIs](#openai-compatible-apis)
5. [Environment Variables Reference](#environment-variables-reference)
6. [Model Comparison](#model-comparison)

---

## OpenAI Models

### Supported Models

- `GPT_3_5_TURBO` - Fast, cost-effective, good for simple projects
- `GPT_4` - High quality, best for complex projects
- `GPT_4_TURBO` - Latest GPT-4 with extended context
- `GPT_4O` - Optimized GPT-4 model
- `GPT_4O_MINI` - Lightweight version of GPT-4o

### Setup

1. **Get API Key:**
   - Visit [OpenAI Platform](https://platform.openai.com/)
   - Create an account or sign in
   - Navigate to API Keys section
   - Create a new API key

2. **Set Environment Variable:**
   ```bash
   # Unix/Linux/macOS
   export OPENAI_API_KEY="sk-your-key-here"
   
   # Windows (PowerShell)
   $env:OPENAI_API_KEY="sk-your-key-here"
   
   # Windows (Command Prompt)
   set OPENAI_API_KEY=sk-your-key-here
   ```

3. **Optional: Custom Base URL**
   For using OpenAI-compatible proxies or regional endpoints:
   ```bash
   export BASE_URL="https://api.openai.com/v1"
   # Or for custom endpoint:
   export BASE_URL="https://your-proxy.com/v1"
   ```

4. **Run ChatDev:**
   ```bash
   python3 run.py --task "Your task" --name "Project" --model "GPT_4O"
   ```

### Cost Considerations

- GPT-3.5-turbo: ~$0.0015 per 1K tokens (input), ~$0.002 per 1K tokens (output)
- GPT-4: ~$0.03 per 1K tokens (input), ~$0.06 per 1K tokens (output)
- GPT-4 Turbo: ~$0.01 per 1K tokens (input), ~$0.03 per 1K tokens (output)
- GPT-4o: ~$0.005 per 1K tokens (input), ~$0.015 per 1K tokens (output)
- GPT-4o-mini: ~$0.00015 per 1K tokens (input), ~$0.0006 per 1K tokens (output)

---

## Google Gemini Models

### Supported Models

- `GEMINI_PRO` - General purpose model
- `GEMINI_PRO_VISION` - Multimodal model with vision capabilities
- `GEMINI_1_5_PRO` - Latest Pro model with extended context (2M tokens)
- `GEMINI_1_5_FLASH` - Fast model with large context (1M tokens)

### Setup

1. **Get API Key:**
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Sign in with your Google account
   - Click "Create API Key"
   - Copy your API key

2. **Install Google Generative AI Library:**
   ```bash
   pip install google-generativeai
   ```

3. **Set Environment Variables:**
   ```bash
   # Unix/Linux/macOS
   export GOOGLE_API_KEY="your-google-api-key"
   export MODEL_PROVIDER="gemini"
   
   # Windows
   $env:GOOGLE_API_KEY="your-google-api-key"
   $env:MODEL_PROVIDER="gemini"
   ```

4. **Run ChatDev:**
   ```bash
   python3 run.py --task "Your task" --name "Project" --model "GEMINI_1_5_PRO"
   ```

### Advantages

- **Free Tier:** Generous free tier for testing
- **Large Context:** Up to 2M tokens context window
- **Multimodal:** Support for text and images (with vision models)
- **Global Availability:** Available in many regions

### Limitations

- May have different response format than OpenAI
- Some features may vary from OpenAI models

---

## DeepSeek Models

### Supported Models

- `DEEPSEEK_CHAT` - General purpose chat model
- `DEEPSEEK_CODER` - Specialized for code generation
- `DEEPSEEK_CHAT_V2` - Latest version with improved performance

### Setup

1. **Get API Key:**
   - Visit [DeepSeek Platform](https://platform.deepseek.com/)
   - Sign up or log in
   - Navigate to API section
   - Create an API key

2. **Set Environment Variables:**
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

3. **Run ChatDev:**
   ```bash
   python3 run.py --task "Your task" --name "Project" --model "DEEPSEEK_CODER"
   ```

### Advantages

- **Cost-Effective:** Lower pricing than OpenAI
- **Code-Focused:** DeepSeek Coder excels at code generation
- **Regional Availability:** Good availability in Asia
- **OpenAI-Compatible:** Uses OpenAI-compatible API format

### Best Use Cases

- Code generation and software development
- Cost-sensitive projects
- Projects requiring frequent API calls

---

## OpenAI-Compatible APIs

Many providers offer OpenAI-compatible APIs, allowing you to use ChatDev with various models through a unified interface.

### Supported Models

- `CLAUDE_3_OPUS` - Anthropic's most capable model
- `CLAUDE_3_SONNET` - Balanced performance model
- `CLAUDE_3_HAIKU` - Fast and cost-effective
- `CLAUDE_3_5_SONNET` - Latest Claude model
- `LLAMA_3_70B` - Meta's Llama 3 (via compatible API)
- `LLAMA_3_8B` - Smaller Llama 3 model
- `MISTRAL_LARGE` - Mistral AI's large model
- `MISTRAL_MEDIUM` - Medium-sized Mistral model
- `MISTRAL_SMALL` - Small, fast Mistral model

### Setup for OpenAI-Compatible APIs

1. **Get API Key from Provider:**
   - Each provider has its own signup process
   - Obtain your API key from the provider's dashboard

2. **Set Environment Variables:**
   ```bash
   # Use OPENAI_API_KEY with your provider's key
   export OPENAI_API_KEY="your-provider-key"
   
   # Set BASE_URL to your provider's endpoint
   export BASE_URL="https://api.provider.com/v1"
   
   # Keep provider as "openai" (uses OpenAI-compatible interface)
   export MODEL_PROVIDER="openai"
   ```

3. **Run ChatDev:**
   ```bash
   python3 run.py --task "Your task" --name "Project" --model "CLAUDE_3_SONNET"
   ```

### Example Providers

**Anthropic Claude (via proxy):**
```bash
export OPENAI_API_KEY="your-claude-key"
export BASE_URL="https://api.anthropic.com/v1"  # If using proxy
export MODEL_PROVIDER="openai"
```

**Local Models (Ollama, vLLM, etc.):**
```bash
export OPENAI_API_KEY="ollama"  # Not always required
export BASE_URL="http://localhost:11434/v1"  # Ollama default
export MODEL_PROVIDER="openai"
```

**Regional Providers:**
```bash
export OPENAI_API_KEY="your-regional-key"
export BASE_URL="https://api.regional-provider.com/v1"
export MODEL_PROVIDER="openai"
```

---

## Environment Variables Reference

### Common Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | API key for OpenAI or compatible APIs | Yes* | - |
| `BASE_URL` | Custom API endpoint URL | No | OpenAI default |
| `MODEL_PROVIDER` | Provider type: "openai", "gemini", "deepseek" | No | "openai" |

### Provider-Specific Variables

#### Google Gemini
| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_API_KEY` | Google AI API key | Yes |

#### DeepSeek
| Variable | Description | Required |
|----------|-------------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek API key | Yes |
| `DEEPSEEK_BASE_URL` | DeepSeek API endpoint | No (default: https://api.deepseek.com/v1) |

### Setting Variables Permanently

**Unix/Linux/macOS (.bashrc/.zshrc):**
```bash
echo 'export OPENAI_API_KEY="your-key"' >> ~/.bashrc
source ~/.bashrc
```

**Windows (System Properties):**
1. Open System Properties → Environment Variables
2. Add new variable under User variables
3. Restart terminal

**Using .env file:**
Create `.env` in ChatDev root:
```
OPENAI_API_KEY=your-key
BASE_URL=https://api.openai.com/v1
MODEL_PROVIDER=openai
```

Then load with:
```bash
export $(cat .env | xargs)
```

---

## Model Comparison

### Performance Comparison

| Model | Speed | Quality | Context | Cost | Best For |
|-------|-------|---------|---------|------|----------|
| GPT-3.5-turbo | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 16K | $ | Simple projects, testing |
| GPT-4 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 8K | $$$$ | Complex projects |
| GPT-4 Turbo | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 128K | $$$ | Large projects |
| GPT-4o | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 128K | $$$ | Balanced performance |
| GPT-4o-mini | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 128K | $ | Cost-effective |
| Gemini Pro | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 32K | Free/$ | General purpose |
| Gemini 1.5 Pro | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 2M | $$ | Large context |
| Gemini 1.5 Flash | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 1M | $ | Fast, large context |
| DeepSeek Chat | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 16K | $ | Cost-effective |
| DeepSeek Coder | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 16K | $ | Code generation |
| Claude 3 Sonnet | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 200K | $$$ | High quality |
| Claude 3 Haiku | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 200K | $ | Fast, quality |

### Regional Availability

| Provider | Americas | Europe | Asia | Other |
|----------|----------|--------|------|-------|
| OpenAI | ✅ | ✅ | ⚠️ | ✅ |
| Google Gemini | ✅ | ✅ | ✅ | ✅ |
| DeepSeek | ⚠️ | ⚠️ | ✅ | ⚠️ |
| Anthropic Claude | ✅ | ✅ | ⚠️ | ⚠️ |

### Cost Comparison (Approximate)

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| GPT-3.5-turbo | $1.50 | $2.00 |
| GPT-4 | $30.00 | $60.00 |
| GPT-4 Turbo | $10.00 | $30.00 |
| GPT-4o | $5.00 | $15.00 |
| GPT-4o-mini | $0.15 | $0.60 |
| Gemini Pro | Free tier available | Free tier available |
| DeepSeek Chat | ~$0.14 | ~$0.28 |
| Claude 3 Sonnet | $3.00 | $15.00 |
| Claude 3 Haiku | $0.25 | $1.25 |

---

## Troubleshooting

### Common Issues

**1. API Key Not Found:**
```bash
# Verify key is set
echo $OPENAI_API_KEY  # or $GOOGLE_API_KEY, etc.

# Re-export if missing
export OPENAI_API_KEY="your-key"
```

**2. Model Not Supported:**
- Check model name spelling (case-sensitive)
- Verify model is in supported list
- Check if provider is correctly configured

**3. Rate Limits:**
- Use models with higher rate limits
- Add delays between requests
- Upgrade API plan
- Switch to different provider

**4. Connection Issues:**
- Check internet connection
- Verify BASE_URL is correct
- Try different provider/region
- Check firewall settings

**5. Import Errors:**
```bash
# Install missing dependencies
pip install google-generativeai  # For Gemini
pip install -r requirements.txt  # For all dependencies
```

---

## Best Practices

1. **Start with Free/Low-Cost Models:**
   - Use GPT-3.5-turbo or Gemini for testing
   - Switch to premium models for production

2. **Monitor Usage:**
   - Set up usage alerts with your provider
   - Track costs regularly
   - Use cost-effective models when possible

3. **Regional Considerations:**
   - Choose providers with servers near you
   - Consider latency for real-time applications
   - Use regional endpoints when available

4. **Model Selection:**
   - Simple projects: GPT-3.5-turbo, Gemini Flash
   - Complex projects: GPT-4, Gemini Pro, Claude
   - Code-focused: DeepSeek Coder
   - Large context: Gemini 1.5 Pro, Claude

5. **Fallback Strategy:**
   - Have multiple API keys ready
   - Configure fallback models
   - Test with different providers

---

## Quick Reference

### Command Examples

```bash
# OpenAI
python3 run.py --task "Build app" --name "App" --model "GPT_4O"

# Gemini
export GOOGLE_API_KEY="key"
python3 run.py --task "Build app" --name "App" --model "GEMINI_1_5_PRO"

# DeepSeek
export DEEPSEEK_API_KEY="key"
python3 run.py --task "Build app" --name "App" --model "DEEPSEEK_CODER"
```

### Environment Setup Script

Create `setup_env.sh`:
```bash
#!/bin/bash
# OpenAI
export OPENAI_API_KEY="your-key"

# Or Gemini
# export GOOGLE_API_KEY="your-key"
# export MODEL_PROVIDER="gemini"

# Or DeepSeek
# export DEEPSEEK_API_KEY="your-key"
# export DEEPSEEK_BASE_URL="https://api.deepseek.com/v1"
# export MODEL_PROVIDER="deepseek"
```

Run: `source setup_env.sh`

---

For more information, see the [TUTORIAL.md](TUTORIAL.md) or [Wiki](wiki.md).

