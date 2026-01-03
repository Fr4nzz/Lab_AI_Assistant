# Claude Code Integration Research Report

## Executive Summary

This document researches integrating Claude models (Opus 4.5 and Sonnet 4.5) into the Lab AI Assistant using **Claude Code CLI with your Max subscription** ($100/month) instead of paying per-token API fees.

**Key Finding:** Claude Code CLI can be invoked programmatically using your Max subscription authentication. This means you pay your flat monthly fee and get to use Claude through this application at no additional cost.

---

## How Claude Code + Max Subscription Works

When you authenticate Claude Code with your Max subscription (`claude login`), it stores OAuth tokens at `~/.claude/oauth_token.json`. These tokens allow Claude Code to make requests using your subscription instead of API credits.

### The Core Technique

The [claude-agent-sdk](https://github.com/anthropics/claude-agent-sdk-python) Python package wraps the Claude Code CLI. By default, if you're logged in with your Max subscription, it uses that authentication.

```python
from claude_agent_sdk import query

async for message in query(prompt="What is 2 + 2?"):
    print(message)  # Uses your Max subscription!
```

### Environment Variables for Forcing Subscription Mode

If the SDK tries to use API keys, you can force subscription mode with these environment variables:

```python
import os

# Remove API key to force subscription auth
if "ANTHROPIC_API_KEY" in os.environ:
    del os.environ["ANTHROPIC_API_KEY"]

# Force subscription mode (optional, usually not needed)
os.environ["CLAUDE_USE_SUBSCRIPTION"] = "true"
```

**Sources:**
- [How I Built claude_max](https://idsc2025.substack.com/p/how-i-built-claude_max-to-unlock)
- [Using Claude Code in Cline](https://cline.bot/blog/how-to-use-your-claude-max-subscription-in-cline)
- [Claude Agent SDK Python](https://github.com/anthropics/claude-agent-sdk-python)

---

## Architecture Comparison

### Option A: n8n + SSH (NetworkChuck approach)
```
┌─────────────┐      ┌─────────────┐      ┌─────────────────────┐
│   n8n       │─SSH─▶│ Linux Server│─────▶│  claude -p "..."    │
│  Workflow   │      │             │      │  (Max subscription) │
└─────────────┘      └─────────────┘      └─────────────────────┘
```
- Requires separate Linux server with SSH
- Added latency from SSH connection
- Complex setup

### Option B: Local Claude Code CLI (OUR APPROACH)
```
┌─────────────┐      ┌─────────────┐      ┌─────────────────────┐
│   WebUI     │─────▶│   FastAPI   │─────▶│  claude-agent-sdk   │
│  (Vue 3)    │      │  Backend    │      │  (subprocess)       │
└─────────────┘      └─────────────┘      └─────────────────────┘
                                                    │
                                                    ▼
                                          ┌─────────────────────┐
                                          │  Claude Code CLI    │
                                          │  (Max subscription) │
                                          └─────────────────────┘
```
- Claude Code installed on same Windows PC
- Direct subprocess invocation (no SSH)
- Uses your existing Max subscription login

**We will use Option B - simpler, faster, no SSH needed.**

---

## Claude Agent SDK Details

### Installation
```bash
pip install claude-agent-sdk
```

Requirements:
- Python 3.10+
- Claude Code CLI installed and authenticated (`claude login`)

### Message Types

The SDK returns these message/content types:

| Type | Description |
|------|-------------|
| `AssistantMessage` | Claude's response with content blocks |
| `TextBlock` | Text content (`.text` attribute) |
| `ToolUseBlock` | Tool invocation (tool name + arguments) |
| `ToolResultBlock` | Tool execution results |
| `ResultMessage` | Final result with metadata |

### Basic Usage Pattern

```python
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import AssistantMessage, TextBlock, ToolUseBlock

async def chat_with_claude(prompt: str):
    options = ClaudeAgentOptions(
        max_turns=10,  # Limit agent iterations
        allowed_tools=["Read", "Write", "Bash"],  # Restrict tools
    )

    full_response = ""
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    full_response += block.text
                elif isinstance(block, ToolUseBlock):
                    print(f"Tool: {block.name}({block.input})")

    return full_response
```

### Custom Tools (MCP Integration)

You can define Python functions as tools Claude can call:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("search_orders", "Search lab orders by patient name", {"patient_name": str})
async def search_orders(args):
    # Your existing order search logic
    results = await search_orders_db(args["patient_name"])
    return {"content": [{"type": "text", "text": str(results)}]}

server = create_sdk_mcp_server(
    name="lab-tools",
    version="1.0.0",
    tools=[search_orders]
)

options = ClaudeAgentOptions(
    mcp_servers={"lab": server},
    allowed_tools=["mcp__lab__search_orders"]
)
```

**Sources:**
- [Claude Agent SDK Reference](https://platform.claude.com/docs/en/agent-sdk/python)
- [DataCamp Claude Agent SDK Tutorial](https://www.datacamp.com/tutorial/how-to-use-claude-agent-sdk)

---

## Headless Mode (CLI Flags)

For direct CLI invocation (alternative to SDK):

```bash
# Basic query
claude -p "Your prompt here"

# With JSON output (for parsing)
claude -p "Your prompt" --output-format json

# With streaming JSON (real-time)
claude -p "Your prompt" --output-format stream-json

# Limit iterations
claude -p "Your prompt" --max-turns 5

# Specify model
claude -p "Your prompt" --model claude-sonnet-4-5-20250929

# Continue previous session
claude -c -p "Follow-up question"
```

**Source:** [Claude Code CLI Commands](https://gist.github.com/dai/51b06d2ed1c1b11a90d16c1a913c96f8)

---

## Integration Architecture for Lab Assistant

### Current Flow (Gemini)
```
User → WebUI → Nuxt API → FastAPI → LangGraph → Gemini API
```

### Proposed Flow (Claude Code + Max)
```
User → WebUI → Nuxt API → FastAPI → ClaudeCodeProvider → claude-agent-sdk → Claude Code CLI
                                           │
                                           └─→ Fallback to Gemini on rate limit
```

### Key Changes

1. **New Provider Class**: `ClaudeCodeProvider` wraps claude-agent-sdk
2. **No LangGraph for Claude**: Claude Code has its own agent loop
3. **Tool Bridging**: Expose existing tools via MCP to Claude Code
4. **Fallback Logic**: If Claude hits Max subscription limits, fall back to Gemini

---

## Rate Limits & Fallback

### Claude Max Subscription Limits
- Max plan has usage limits (not publicly documented exact numbers)
- When limits are hit, Claude Code shows rate limit messages
- The SDK will raise errors we can catch

### Fallback Strategy
```python
class ClaudeCodeProvider:
    async def invoke(self, messages):
        try:
            return await self._invoke_claude(messages)
        except (RateLimitError, ProcessError) as e:
            if "rate limit" in str(e).lower():
                logger.warning("Claude Max limit hit, falling back to Gemini")
                return await self._invoke_gemini_fallback(messages)
            raise
```

---

## Image Rotation Decision

**Keep with Gemini 3 Flash** - Reasons:
1. **Fast & cheap**: Uses free tier with key rotation
2. **Simple task**: Just needs to detect rotation angle
3. **Already working**: No need to change
4. **Saves Claude quota**: Reserve Claude for complex reasoning

---

## Comparison: Claude Code vs Direct API

| Feature | Claude Code + Max | Direct API |
|---------|-------------------|------------|
| **Cost** | $100/month flat | ~$15-75/million tokens |
| **Authentication** | OAuth (subscription) | API key |
| **Tool Support** | Built-in + MCP custom | LangChain tools |
| **Agent Loop** | Built-in | Manual with LangGraph |
| **Streaming** | AsyncIterator | SSE |
| **Best For** | Heavy usage | Pay-per-use |

**Verdict:** For your use case with Max subscription, Claude Code is significantly more cost-effective.

---

## Prerequisites

### On the Windows PC running Lab Assistant:

1. **Install Claude Code CLI**
   ```powershell
   npm install -g @anthropic-ai/claude-code
   ```

2. **Authenticate with Max subscription**
   ```bash
   claude login
   ```
   This opens browser for OAuth login. Use your Max account.

3. **Verify authentication**
   ```bash
   claude -p "Hello, what model are you?"
   ```

4. **Install Python SDK**
   ```bash
   pip install claude-agent-sdk
   ```

---

# Implementation Plan

## Phase 1: Setup & Basic Integration

### Step 1.1: Install Claude Code on Windows
```powershell
# In PowerShell (Administrator)
npm install -g @anthropic-ai/claude-code

# Login with Max subscription
claude login

# Verify it works
claude -p "Say hello"
```

### Step 1.2: Add Python Dependencies
**File:** `backend/requirements.txt`

Add:
```
claude-agent-sdk>=0.1.0
```

### Step 1.3: Create ClaudeCodeProvider
**File:** `backend/claude_provider.py` (new file)

```python
"""
Claude Code Provider - Uses Max subscription via Claude Code CLI.
No API key needed - uses your authenticated Claude Code installation.
"""
import asyncio
import logging
from typing import List, Optional, AsyncIterator, Dict, Any
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import (
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ResultMessage
)

logger = logging.getLogger(__name__)


class ClaudeCodeProvider:
    """
    Wraps claude-agent-sdk for use with Max subscription.
    Falls back to Gemini if Claude is unavailable.
    """

    def __init__(
        self,
        model: str = "claude-opus-4-5-20250514",
        max_turns: int = 20,
        gemini_fallback = None
    ):
        self.model = model
        self.max_turns = max_turns
        self.gemini_fallback = gemini_fallback

    async def invoke(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Send messages to Claude Code and stream response.

        Yields dict events:
        - {"type": "text", "content": "..."}
        - {"type": "tool_call", "name": "...", "input": {...}}
        - {"type": "tool_result", "output": "..."}
        - {"type": "done", "result": {...}}
        """
        try:
            # Convert messages to prompt format
            prompt = self._messages_to_prompt(messages)

            options = ClaudeAgentOptions(
                max_turns=self.max_turns,
                # Don't allow file/bash tools in chat context
                allowed_tools=[],
            )

            async for message in query(prompt=prompt, options=options):
                async for event in self._process_message(message):
                    yield event

        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "quota" in error_str:
                logger.warning(f"Claude Max limit hit: {e}")
                if self.gemini_fallback:
                    logger.info("Falling back to Gemini")
                    async for event in self._gemini_fallback_invoke(messages):
                        yield event
                else:
                    yield {"type": "error", "message": str(e)}
            else:
                raise

    async def _process_message(self, message) -> AsyncIterator[Dict[str, Any]]:
        """Convert SDK message to our event format."""
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    yield {"type": "text", "content": block.text}
                elif isinstance(block, ToolUseBlock):
                    yield {
                        "type": "tool_call",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    }
                elif isinstance(block, ToolResultBlock):
                    yield {
                        "type": "tool_result",
                        "id": block.tool_use_id,
                        "output": block.content
                    }
        elif isinstance(message, ResultMessage):
            yield {
                "type": "done",
                "result": {
                    "duration_ms": message.duration_ms,
                    "num_turns": message.num_turns,
                    "session_id": message.session_id
                }
            }

    def _messages_to_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """Convert chat messages to a single prompt for Claude Code."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                # Handle multimodal content
                text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                content = "\n".join(text_parts)
            parts.append(f"{role.upper()}: {content}")
        return "\n\n".join(parts)

    async def _gemini_fallback_invoke(self, messages):
        """Fallback to Gemini when Claude is unavailable."""
        if not self.gemini_fallback:
            yield {"type": "error", "message": "No fallback available"}
            return

        # Use existing Gemini implementation
        response = await self.gemini_fallback.ainvoke(messages)
        yield {"type": "text", "content": response.content}
        yield {"type": "done", "result": {"fallback": True}}
```

---

## Phase 2: Integrate with Backend

### Step 2.1: Update Model Configuration
**File:** `backend/server.py`

Add Claude models to available models:
```python
AVAILABLE_MODELS = [
    "claude-opus-4-5",      # Claude Opus 4.5 via Claude Code (default)
    "claude-sonnet-4-5",    # Claude Sonnet 4.5 via Claude Code
    "gemini-3-flash-preview",  # Gemini (fallback)
    "gemini-flash-latest",
]
DEFAULT_MODEL = "claude-opus-4-5"
```

### Step 2.2: Create Claude Endpoint
**File:** `backend/server.py`

Add new endpoint for Claude Code streaming:
```python
from claude_provider import ClaudeCodeProvider

# Initialize provider
claude_provider = ClaudeCodeProvider(
    model="claude-opus-4-5-20250514",
    gemini_fallback=get_chat_model(model_name="gemini-3-flash-preview")
)

@app.post("/api/chat/claude")
async def chat_claude(request: AISdkChatRequest):
    """Stream chat using Claude Code (Max subscription)."""

    async def generate():
        async for event in claude_provider.invoke(request.messages):
            # Convert to AI SDK stream format
            if event["type"] == "text":
                yield f'data: {{"type":"text-delta","delta":"{event["content"]}"}}\n\n'
            elif event["type"] == "tool_call":
                yield f'data: {{"type":"tool-call","..."}}\n\n'
            elif event["type"] == "done":
                yield 'data: [DONE]\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Step 2.3: Route Models to Providers
**File:** `backend/server.py`

Update the `/api/chat/aisdk` endpoint to route based on model:
```python
@app.post("/api/chat/aisdk")
async def chat_aisdk(request: AISdkChatRequest):
    model = request.model or DEFAULT_MODEL

    if model.startswith("claude-"):
        # Use Claude Code provider
        return await chat_claude(request)
    else:
        # Use existing Gemini/LangGraph implementation
        return await chat_gemini(request)
```

---

## Phase 3: Frontend Model Selection

### Step 3.1: Update Model Configs
**File:** `frontend-nuxt/app/composables/useModels.ts`

```typescript
export const MODEL_CONFIGS: ModelConfig[] = [
  {
    id: 'claude-opus-4-5',
    displayName: 'Lab Assistant (Claude Opus 4.5)',
    icon: 'i-lucide-brain',
    isLabAssistant: true
  },
  {
    id: 'claude-sonnet-4-5',
    displayName: 'Lab Assistant (Claude Sonnet 4.5)',
    icon: 'i-lucide-zap',
    isLabAssistant: true
  },
  {
    id: 'gemini-3-flash-preview',
    displayName: 'Lab Assistant (Gemini 3 Flash)',
    icon: 'i-lucide-flask-conical',
    isLabAssistant: true
  },
]
```

### Step 3.2: Update Telegram Bot
**File:** `telegram_bot/keyboards/inline.py`

```python
AVAILABLE_MODELS = {
    "claude-opus-4-5": "🧠 Claude Opus 4.5 (más inteligente)",
    "claude-sonnet-4-5": "⚡ Claude Sonnet 4.5 (rápido)",
    "gemini-3-flash-preview": "🔬 Gemini 3 Flash (respaldo)",
}
DEFAULT_MODEL = "claude-opus-4-5"
```

---

## Phase 4: Custom Tools via MCP

### Step 4.1: Expose Existing Tools to Claude Code
**File:** `backend/claude_tools.py` (new file)

```python
"""
MCP tools for Claude Code - bridges our existing tools to Claude's MCP format.
"""
from claude_agent_sdk import tool, create_sdk_mcp_server
from graph.tools import (
    search_order_from_database,
    navigate_to_order,
    # ... other tools
)

@tool("search_orders", "Search for lab orders by patient name", {"patient_name": str})
async def mcp_search_orders(args):
    """Wrapper for existing search_order_from_database tool."""
    result = await search_order_from_database(args["patient_name"])
    return {"content": [{"type": "text", "text": str(result)}]}

@tool("navigate_to_order", "Navigate to a specific order in the lab system", {"order_number": str})
async def mcp_navigate_to_order(args):
    """Wrapper for existing navigate_to_order tool."""
    result = await navigate_to_order(args["order_number"])
    return {"content": [{"type": "text", "text": str(result)}]}

# Create MCP server with all tools
lab_mcp_server = create_sdk_mcp_server(
    name="lab-assistant",
    version="1.0.0",
    tools=[
        mcp_search_orders,
        mcp_navigate_to_order,
        # Add more tools...
    ]
)
```

### Step 4.2: Update ClaudeCodeProvider with Tools
**File:** `backend/claude_provider.py`

```python
from claude_tools import lab_mcp_server

options = ClaudeAgentOptions(
    max_turns=self.max_turns,
    mcp_servers={"lab": lab_mcp_server},
    allowed_tools=[
        "mcp__lab__search_orders",
        "mcp__lab__navigate_to_order",
        # ... more tools
    ]
)
```

---

## Phase 5: Testing

### Step 5.1: Test Claude Code Directly
```bash
# On Windows, in the Lab_AI_Assistant directory
claude -p "Hello, are you using my Max subscription?"
```

### Step 5.2: Test Python SDK
```python
# backend/test_claude_code.py
import anyio
from claude_agent_sdk import query

async def test():
    async for msg in query(prompt="Say 'Claude Code working!'"):
        print(msg)

anyio.run(test)
```

### Step 5.3: Test Full Integration
```bash
# Start backend
python -m uvicorn server:app --reload

# In another terminal, test endpoint
curl -X POST http://localhost:8000/api/chat/claude \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

---

## Implementation Priority

| Priority | Task | Effort | Status |
|----------|------|--------|--------|
| 1 | Install Claude Code CLI on Windows | 10 min | Required |
| 2 | Authenticate with Max subscription | 5 min | Required |
| 3 | Add `claude-agent-sdk` to requirements | 5 min | Required |
| 4 | Create `ClaudeCodeProvider` class | 2 hours | Core |
| 5 | Update `/api/chat/aisdk` routing | 1 hour | Core |
| 6 | Update frontend model configs | 15 min | UX |
| 7 | Update Telegram bot models | 15 min | UX |
| 8 | Create MCP tool wrappers | 2 hours | Optional |
| 9 | Test integration end-to-end | 1 hour | Verification |

**Total Estimated Effort: ~6-8 hours**

---

## Important Notes

1. **Claude Code must be installed and authenticated** on the PC running Lab Assistant
2. **No API key needed** - uses your Max subscription OAuth tokens
3. **Image rotation stays with Gemini** - saves Claude quota for reasoning
4. **Fallback is automatic** - if Claude hits limits, falls back to Gemini
5. **Different agent loop** - Claude Code has its own agentic capabilities, doesn't use LangGraph

---

## References

1. [NetworkChuck n8n + Claude Code Guide](https://github.com/theNetworkChuck/n8n-claude-code-guide)
2. [How I Built claude_max](https://idsc2025.substack.com/p/how-i-built-claude_max-to-unlock)
3. [Claude Agent SDK Python](https://github.com/anthropics/claude-agent-sdk-python)
4. [Claude Code Headless Mode](https://code.claude.com/docs/en/headless)
5. [Using Claude Max in Cline](https://cline.bot/blog/how-to-use-your-claude-max-subscription-in-cline)
6. [Claude Code CLI Commands Reference](https://gist.github.com/dai/51b06d2ed1c1b11a90d16c1a913c96f8)
7. [Claude Code is Programmable](https://github.com/disler/claude-code-is-programmable)
