# Open Notebook with Claude Code (Max Subscription)

This guide explains how to run [Open Notebook](https://github.com/lfnovo/open-notebook) using your Claude Max subscription via Claude Code, without needing any API keys for the LLM.

## Overview

Open Notebook is an open-source alternative to Google's NotebookLM that allows you to:
- Upload PDFs, videos, audio files, and web pages
- Chat with your documents using AI
- Generate professional multi-speaker podcasts from your content

Instead of paying for API keys, we use **Claude Code** with your **Max subscription** as the AI backend.

## Prerequisites

- **Claude Max subscription** (logged in via Claude Code)
- **Docker Desktop** installed and running
- **Python 3.10+** installed
- **Claude Code CLI** installed: `npm install -g @anthropic-ai/claude-code`
- **Authenticated Claude Code**: Run `claude` once and log in

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Computer                         │
│                                                          │
│  ┌──────────────────┐     ┌─────────────────────────┐   │
│  │ Claude Code      │     │ Docker                  │   │
│  │ Proxy (local)    │◄────┤                         │   │
│  │ Port 8080        │     │  ┌─────────────────┐    │   │
│  │                  │     │  │ Open Notebook   │    │   │
│  │ Uses your Max    │     │  │ Port 8502 (UI)  │    │   │
│  │ subscription     │     │  │ Port 5055 (API) │    │   │
│  └──────────────────┘     │  └────────┬────────┘    │   │
│           │               │           │             │   │
│           │               │  ┌────────▼────────┐    │   │
│           ▼               │  │ SurrealDB       │    │   │
│  ┌──────────────────┐     │  │ Port 8000       │    │   │
│  │ Claude (Cloud)   │     │  └─────────────────┘    │   │
│  │ via Max          │     └─────────────────────────┘   │
│  └──────────────────┘                                   │
└─────────────────────────────────────────────────────────┘
```

## Installation

### Step 1: Start the Claude Code Proxy

First, start the proxy that converts Claude Code into an OpenAI-compatible API:

**Windows:**
```cmd
cd open-notebook\claude-code-proxy
run.bat
```

**Linux/macOS:**
```bash
cd open-notebook/claude-code-proxy
chmod +x run.sh
./run.sh
```

You should see:
```
Starting Claude Code Proxy on http://localhost:8080
```

**Keep this terminal running!**

### Step 2: Start Open Notebook

In a **new terminal**, start the Docker containers:

```bash
cd open-notebook
docker compose up -d
```

Wait 15-30 seconds for everything to start.

### Step 3: Verify Installation

1. **Check proxy health:**
   ```bash
   curl http://localhost:8080/health
   ```
   Should return: `{"status":"healthy","sdk_available":true,"default_model":"sonnet"}`

2. **Access Open Notebook:**
   Open http://localhost:8502 in your browser

## Setting Up Models in Open Notebook

After starting, you need to configure the AI models:

1. Go to **Settings** (gear icon) in Open Notebook
2. Click **AI Models**
3. Add a new model:
   - **Provider**: `openai_compatible`
   - **Model ID**: `claude-sonnet` (or `claude-opus` for better quality)
   - **Model Type**: `language_model`
4. Set it as the **default** for language tasks

### Note on Embeddings

Claude Code doesn't provide embeddings. You have three options:

**Option A: Use OpenAI (requires API key)**
Add to docker-compose.yml:
```yaml
- OPENAI_API_KEY=sk-your-key
```

**Option B: Use Ollama (free, local)**
Uncomment the ollama service in docker-compose.yml, then:
```bash
docker compose up -d
docker exec open-notebook-ollama ollama pull nomic-embed-text
```

**Option C: Use Voyage AI (free tier available)**
Get a free key from https://www.voyageai.com/ and add:
```yaml
- VOYAGE_API_KEY=your-key
```

## Creating a Podcast from a PDF

### Step 1: Create a Notebook

1. Click **"+ New Notebook"** in Open Notebook
2. Give it a name (e.g., "Research Paper Podcast")
3. Click **Create**

### Step 2: Upload Your PDF

1. Open your notebook
2. Click **"+ Add Source"**
3. Select **"Upload File"**
4. Choose your PDF file
5. Wait for processing (the AI will extract and analyze the content)

### Step 3: Review the Content

1. After processing, you'll see the PDF content in your notebook
2. You can chat with it to understand the key points:
   - "What are the main findings?"
   - "Summarize this in 5 bullet points"
   - "What are the most interesting insights?"

### Step 4: Generate the Podcast

1. Click the **"Podcast"** tab or button
2. Configure your podcast:
   - **Number of speakers**: 1-4 (choose 2 for a conversation style)
   - **Speaker profiles**: Customize names and personalities
   - **Episode length**: Short (5 min), Medium (10 min), or Long (15+ min)
   - **Style**: Casual, Educational, Interview, etc.

3. Click **"Generate Podcast"**
4. Wait for generation (this may take a few minutes with Claude)

### Step 5: Download Your Podcast

1. Once generated, preview the podcast
2. Click **Download** to save the audio file
3. The script/transcript is also available

## Using Claude Opus (Better Quality)

By default, the proxy uses Claude Sonnet. For better podcast quality, use Opus:

1. Stop the proxy (Ctrl+C)
2. Set the environment variable:

   **Windows:**
   ```cmd
   set CLAUDE_MODEL=opus
   run.bat
   ```

   **Linux/macOS:**
   ```bash
   export CLAUDE_MODEL=opus
   ./run.sh
   ```

3. In Open Notebook settings, create a model with ID `claude-opus`

## Troubleshooting

### "Claude Agent SDK not available"

Install the SDK:
```bash
pip install claude-agent-sdk
```

### "Connection refused" from Docker

Make sure the Claude Code proxy is running on your host machine (not in Docker).

### Slow responses

- Claude Code can take 30-60 seconds for complex requests
- The timeout is set to 120 seconds by default
- Use Sonnet for faster responses, Opus for better quality

### Authentication errors

Make sure you're logged into Claude Code:
```bash
claude --version  # Should show version
claude -p "Hello"  # Should respond
```

If not authenticated:
```bash
claude login
```

## Stopping Everything

```bash
# Stop Open Notebook (Docker)
docker compose down

# Stop Claude Code proxy
# Press Ctrl+C in the terminal running run.bat/run.sh
```

## Useful Commands

```bash
# View logs
docker compose logs -f open_notebook

# Restart Open Notebook
docker compose restart

# Update to latest version
docker compose pull
docker compose up -d

# Reset all data (WARNING: deletes everything)
docker compose down -v
```

## Resources

- [Open Notebook GitHub](https://github.com/lfnovo/open-notebook)
- [Open Notebook Documentation](https://www.open-notebook.ai/)
- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [Claude Max Subscription](https://www.anthropic.com/claude)
