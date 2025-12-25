#!/bin/bash
# Setup script for LobeChat frontend

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Setting up LobeChat frontend..."

# Clone LobeChat if not exists
if [ ! -d "$PROJECT_DIR/frontend-lobechat" ]; then
    echo "Cloning LobeChat..."
    git clone https://github.com/lobehub/lobe-chat.git "$PROJECT_DIR/frontend-lobechat"
fi

cd "$PROJECT_DIR/frontend-lobechat"

# Create plugin directory
mkdir -p public/plugins/lab-assistant

# Copy plugin manifest
cat > public/plugins/lab-assistant/manifest.json << 'EOF'
{
  "$schema": "https://chat-plugins.lobehub.com/schema/manifest.json",
  "identifier": "lab-assistant",
  "version": "2.0.0",
  "type": "standalone",
  "api": [
    {
      "url": "http://localhost:8000/api/chat",
      "name": "sendMessage",
      "description": "Send a message to the lab assistant"
    },
    {
      "url": "http://localhost:8000/api/browser/screenshot",
      "name": "getScreenshot",
      "description": "Get current browser screenshot"
    }
  ],
  "meta": {
    "title": "Lab Assistant",
    "description": "Laboratory result entry assistant with browser automation",
    "avatar": "https://raw.githubusercontent.com/lobehub/lobe-chat/main/public/images/favicon.ico",
    "tags": ["laboratory", "automation", "healthcare"]
  }
}
EOF

# Create .env.local if not exists
if [ ! -f ".env.local" ]; then
    cat > .env.local << 'EOF'
# Custom Backend (Lab Assistant API)
OPENAI_PROXY_URL=http://localhost:8000/v1
OPENAI_API_KEY=dummy-key-for-local
OPENAI_MODEL_LIST=+lab-assistant=Lab Assistant<100000:vision:fc>

# Google Gemini (add your key)
# GOOGLE_API_KEY=your-key-here

# Enable features
FEATURE_FLAGS={"enableArtifacts":true,"enablePlugins":true}
EOF
    echo "Created .env.local - please add your API keys"
fi

# Install dependencies
echo "Installing dependencies..."
if command -v pnpm &> /dev/null; then
    pnpm install
elif command -v npm &> /dev/null; then
    npm install
else
    echo "Please install pnpm or npm first"
    exit 1
fi

echo ""
echo "Frontend setup complete!"
echo ""
echo "To start the frontend:"
echo "  cd frontend-lobechat && pnpm dev"
echo ""
echo "To start the backend:"
echo "  cd backend && python server.py"
