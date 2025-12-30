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
User (Nuxt) → FastAPI Backend → Gemini AI → Playwright Browser
                                      ↓
                           Tool calls (search, edit, etc.)
                                      ↓
                           Browser fills forms
                                      ↓
                           User clicks "Save"
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Microsoft Edge browser installed

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
```

### 3. Start

**Double-click `Lab_Assistant.bat`** (Windows)

The launcher will:
- Check for Python and Node.js (offer to install if missing)
- Install all dependencies automatically
- Start Backend, Frontend, and optionally Telegram Bot

### 4. Open the app

1. Browser opens automatically to http://localhost:3000
2. Login to the lab system in the browser window that opens
3. Start chatting!

### Optional: Desktop Shortcut & Autostart

```batch
# Create desktop shortcut with icon
.\setup-shortcut.bat

# Enable autostart on PC boot
.\setup-autostart.bat
```

## Configuration

### Environment Variables (`.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `GEMINI_API_KEYS` | Comma-separated Gemini API keys | `key1,key2,key3` |
| `GEMINI_MODEL` | Model to use | `gemini-2.0-flash` |
| `BROWSER_CHANNEL` | Browser to use | `msedge`, `chrome`, `chromium` |
| `TARGET_URL` | Lab system URL | `https://laboratoriofranz.orion-labs.com/` |
| `OPENROUTER_API_KEY` | For chat title naming | `sk-or-v1-xxx` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | `123456:ABC...` |

## Usage

1. Open http://localhost:3000
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
│   ├── server.py           # FastAPI server
│   ├── models.py           # Gemini wrapper with key rotation
│   ├── browser_manager.py  # Playwright browser control
│   ├── prompts.py          # System prompt
│   └── graph/
│       ├── agent.py        # LangGraph agent
│       └── tools.py        # Tool definitions
├── frontend-nuxt/
│   ├── app/                # Nuxt app (components, pages)
│   └── server/             # Server API routes
├── telegram_bot/           # Telegram bot integration
├── Lab_Assistant.bat       # Windows launcher
├── setup-shortcut.bat      # Create desktop shortcut
├── setup-autostart.bat     # Enable autostart on boot
├── .env.example            # Example configuration
└── README.md
```

## Troubleshooting

### Port already in use

```bash
# Find what's using the port
netstat -ano | findstr :8000
# Kill the process
taskkill /PID <PID> /F
```

### Rate limits (429 errors)

Add more API keys to `GEMINI_API_KEYS` in `.env`. The system rotates automatically.

### Browser not opening

Make sure Microsoft Edge is installed, or change `BROWSER_CHANNEL` to `chrome` or `chromium`.

## Remote Access & Authentication

Want to access Lab Assistant from anywhere (not just your local network)?

See **[Remote Access Setup Guide](docs/REMOTE_ACCESS_SETUP.md)** for:
- Cloudflare Tunnel setup (expose to internet)
- Google OAuth authentication
- Admin and user access control
- All required API keys and where to get them

## License

MIT
