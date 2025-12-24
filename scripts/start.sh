#!/bin/bash
# Start both backend and frontend for Lab Assistant

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Check if frontend exists, if not set it up
if [ ! -d "$PROJECT_DIR/frontend-lobechat" ]; then
    echo -e "${YELLOW}Frontend not found. Running setup...${NC}"
    "$SCRIPT_DIR/setup-frontend.sh"
fi

# Start backend
echo -e "${GREEN}Starting backend on http://localhost:8000${NC}"
cd "$PROJECT_DIR/backend"
python server.py &
BACKEND_PID=$!

# Wait for backend to be ready
echo -e "${YELLOW}Waiting for backend to start...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}Backend ready!${NC}"
        break
    fi
    sleep 1
done

# Start frontend
echo -e "${GREEN}Starting frontend on http://localhost:3210${NC}"
cd "$PROJECT_DIR/frontend-lobechat"
if command -v pnpm &> /dev/null; then
    pnpm dev &
elif command -v npm &> /dev/null; then
    npm run dev &
else
    echo -e "${RED}Error: pnpm or npm required${NC}"
    cleanup
fi
FRONTEND_PID=$!

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Lab Assistant is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Backend:  ${YELLOW}http://localhost:8000${NC}"
echo -e "Frontend: ${YELLOW}http://localhost:3210${NC}"
echo ""
echo -e "Press ${RED}Ctrl+C${NC} to stop both services"
echo ""

# Wait for processes
wait
