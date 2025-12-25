# Lab Assistant AI

AI-powered assistant for clinical laboratory staff to enter exam results in laboratoriofranz.orion-labs.com.

## Features

- **AI Chat**: Send text, notebook images, or audio with instructions
- **Browser Automation**: AI controls the browser to fill forms (but NEVER saves)
- **Tool Calling**: 8 specialized tools (search_orders, edit_results, etc.)
- **Safe**: AI only fills forms - user must click "Save" to confirm
- **Multi-key Rotation**: Automatic API key rotation on rate limits

## Architecture

```
User (LobeChat) → FastAPI Backend → Gemini AI → Playwright Browser
                                         ↓
                              Tool calls (search, edit, etc.)
                                         ↓
                              Browser fills forms
                                         ↓
                              User clicks "Save"
```

## Quick Start (Docker)

### 1. Clone and configure

```bash
git clone https://github.com/yourusername/Lab_AI_Assistant.git
cd Lab_AI_Assistant

# Copy example config
cp .env.example .env
```

### 2. Edit `.env` file

```bash
# Required: Gemini API keys (get from https://aistudio.google.com/apikey)
GEMINI_API_KEYS=key1,key2,key3

# Optional: OpenRouter for LobeChat topic naming (https://openrouter.ai/keys)
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

### 3. Start with Docker

```bash
docker-compose up -d
```

This starts:
- **Backend** on http://localhost:8000 (Lab Assistant API)
- **LobeChat** on http://localhost:3210 (Chat UI)

### 4. Open LobeChat

1. Go to http://localhost:3210
2. Create a new chat
3. Select **"Lab Assistant"** as the model
4. Start chatting!

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- Microsoft Edge browser installed

### 1. Setup

```powershell
# Clone
git clone https://github.com/yourusername/Lab_AI_Assistant.git
cd Lab_AI_Assistant

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend/requirements.txt

# Copy and edit config
cp .env.example .env
# Edit .env with your GEMINI_API_KEYS
```

### 2. Run Backend

```powershell
cd backend
python server.py
```

Backend runs on http://localhost:8000

### 3. Run LobeChat (Docker)

```bash
docker run -d -p 3210:3210 \
  -e OPENAI_PROXY_URL=http://host.docker.internal:8000/v1 \
  -e OPENAI_API_KEY=dummy \
  -e "OPENAI_MODEL_LIST=-all,+lab-assistant=Lab Assistant<100000:vision:fc>" \
  lobehub/lobe-chat:latest
```

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GEMINI_API_KEYS` | Comma-separated Gemini API keys | `key1,key2,key3` |
| `GEMINI_MODEL` | Model to use | `gemini-2.0-flash` |
| `OPENROUTER_API_KEY` | For LobeChat topic naming | `sk-or-v1-xxx` |
| `BROWSER_CHANNEL` | Browser to use | `msedge`, `chrome`, `chromium` |
| `TARGET_URL` | Lab system URL | `https://laboratoriofranz.orion-labs.com/` |

### LobeChat Model Selection

In LobeChat Settings → System Assistant:
- **Topic Naming Model**: Use OpenRouter free model (e.g., `meta-llama/llama-3.2-3b-instruct:free`)
- **Default Chat Model**: Use `lab-assistant` (your backend)

## Usage

1. Open http://localhost:3210
2. Login to the lab system in the browser window that opens
3. Send a message like: *"busca las ordenes de Juan Perez y llena la hemoglobina con 15.5"*
4. AI will:
   - Search for orders
   - Open the report page
   - Fill the field
   - Highlight changes
5. **Review and click "Save" in the browser**

## AI Tools

| Tool | Description |
|------|-------------|
| `search_orders` | Search orders by patient name or ID |
| `get_exam_fields` | Get exam fields for one or more orders |
| `get_order_details` | Get order details by ID |
| `edit_results` | Fill multiple fields across orders |
| `add_exam_to_order` | Add exam to an existing order |
| `create_new_order` | Create new order for patient |
| `highlight_fields` | Highlight fields in browser |
| `ask_user` | Ask user for clarification |

## Project Structure

```
Lab_AI_Assistant/
├── backend/
│   ├── server.py           # FastAPI server (OpenAI-compatible)
│   ├── models.py           # Gemini wrapper with key rotation
│   ├── browser_manager.py  # Playwright browser control
│   ├── prompts.py          # System prompt
│   └── graph/
│       ├── agent.py        # LangGraph agent
│       └── tools.py        # Tool definitions
├── docker-compose.yml      # Docker setup
├── .env.example            # Example configuration
└── README.md
```

## Troubleshooting

### Port already in use

```bash
# Find what's using the port
netstat -ano | findstr :3210
# Kill the process
taskkill /PID <PID> /F
```

### Rate limits (429 errors)

Add more API keys to `GEMINI_API_KEYS` in `.env`. The system rotates automatically.

### Browser not opening

Make sure Microsoft Edge is installed, or change `BROWSER_CHANNEL` to `chrome` or `chromium`.

## License

MIT
