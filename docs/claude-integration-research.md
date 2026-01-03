# Claude Integration Research Report

## Executive Summary

This document researches the feasibility of integrating Claude models (Opus 4.5 and Sonnet 4.5) into the Lab AI Assistant application. After extensive research, **direct Anthropic API integration is the recommended approach** rather than using Claude Code SDK.

## Key Findings

### Option 1: Claude Code / Claude Agent SDK (NOT Recommended)

The [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) (formerly Claude Code SDK) allows running Claude Code as a subprocess:

```python
from claude_agent_sdk import query

async for message in query(prompt="What is 2 + 2?"):
    print(message)
```

**Why NOT recommended for this project:**
- **Designed for code-assistant workflows**, not general chat with tool calling
- **Subprocess-based**: Spawns Claude Code CLI as a subprocess, adding latency
- **Different tool paradigm**: Uses MCP (Model Context Protocol) servers, incompatible with our LangChain tools
- **No direct streaming control**: Would require significant refactoring of our streaming architecture
- **Overhead**: Bundles full Claude Code CLI (file editing, bash execution, etc.) - overkill for our use case

**Sources:**
- [Claude Agent SDK Overview](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Claude Code Headless Mode](https://docs.claude.com/en/docs/claude-code/sdk/sdk-headless)
- [GitHub - anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python)

---

### Option 2: Direct Anthropic API (RECOMMENDED)

Direct API integration using:
1. **Backend (LangGraph)**: `langchain-anthropic` package with `ChatAnthropic`
2. **Frontend (AI SDK)**: `@ai-sdk/anthropic` provider

This approach:
- **Drop-in compatible** with existing LangGraph agent architecture
- **Same tool binding pattern** as current Gemini implementation
- **Native streaming** via AI SDK Data Stream Protocol
- **Extended thinking support** for reasoning tasks

**Sources:**
- [LangChain ChatAnthropic Documentation](https://python.langchain.com/docs/integrations/chat/anthropic/)
- [AI SDK Anthropic Provider](https://ai-sdk.dev/providers/ai-sdk-providers/anthropic)
- [Vercel + Anthropic Collaboration](https://vercel.com/blog/collaborating-with-anthropic-on-claude-sonnet-4-5)

---

## Model Availability

| Model | Model ID | Context Window | Best For |
|-------|----------|----------------|----------|
| **Claude Opus 4.5** | `claude-opus-4-5-20250514` | 200K (1M beta) | Complex reasoning, coding, agents |
| **Claude Sonnet 4.5** | `claude-sonnet-4-5-20250929` | 200K (1M beta) | Fast agentic tasks, coding |
| **Claude Sonnet 4** | `claude-sonnet-4-20250514` | 200K | Balanced performance/cost |

**Source:** [Anthropic Models Overview](https://platform.claude.com/docs/en/about-claude/models/overview)

---

## Integration Architecture

### Current Architecture (Gemini)
```
┌─────────────┐      ┌─────────────┐      ┌─────────────────────┐
│   WebUI     │─────▶│   Nuxt API  │─────▶│  FastAPI Backend    │
│  (Vue 3)    │      │ (AI SDK)    │      │  (LangGraph)        │
└─────────────┘      └─────────────┘      └─────────────────────┘
                                                    │
                                                    ▼
                                          ┌─────────────────────┐
                                          │ ChatGoogleGenerativeAI │
                                          │  (with Key Rotation)  │
                                          └─────────────────────┘
```

### Proposed Architecture (Multi-Provider with Fallback)
```
┌─────────────┐      ┌─────────────┐      ┌─────────────────────┐
│   WebUI     │─────▶│   Nuxt API  │─────▶│  FastAPI Backend    │
│  (Vue 3)    │      │ (AI SDK)    │      │  (LangGraph)        │
└─────────────┘      └─────────────┘      └─────────────────────┘
       │                                           │
       │                                           ▼
       │                              ┌────────────────────────┐
       │                              │  Model Provider Router │
       │                              │  (with Fallback Logic) │
       │                              └────────────────────────┘
       │                                    │           │
       │                                    ▼           ▼
       │                         ┌──────────────┐  ┌──────────────┐
       │                         │ ChatAnthropic │  │ ChatGemini   │
       │                         │ (Opus/Sonnet) │  │ (Fallback)   │
       │                         └──────────────┘  └──────────────┘
       │
       └──────────▶ Image Rotation ──────────▶ Gemini 3 Flash (unchanged)
```

---

## Rate Limiting & Fallback Strategy

### Anthropic Rate Limits
- **429 Error**: Rate limit exceeded (includes `retry-after` header)
- **529 Error**: Server overload (temporary, resolves in seconds)

### Proposed Fallback Logic
```python
class ModelProviderRouter:
    """Routes to Claude (primary) with Gemini fallback."""

    async def invoke(self, messages):
        try:
            return await self.claude_model.ainvoke(messages)
        except (RateLimitError, OverloadedError) as e:
            logger.warning(f"Claude unavailable: {e}, falling back to Gemini")
            return await self.gemini_fallback.ainvoke(messages)
```

**Source:** [Anthropic Rate Limits Documentation](https://docs.claude.com/en/api/rate-limits)

---

## Image Rotation Decision

**Keep with Gemini 3 Flash** - Reasons:
1. **Fast & cheap**: Uses `thinking_level="minimal"` for sub-1s detection
2. **Already working**: No need to change working code
3. **Vision-optimized**: Gemini excels at simple image analysis tasks
4. **API key rotation**: Existing rotation logic handles rate limits

---

## LangGraph Integration Details

### Current Gemini Tool Binding
```python
# backend/graph/agent.py (current)
model = get_chat_model(model_name=model_name)
model_with_tools = model.bind_tools(tools)
```

### Proposed Claude Tool Binding
```python
# backend/graph/agent.py (proposed)
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(
    model="claude-opus-4-5-20250514",
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
    temperature=0.7,
    max_tokens=4096,
)
model_with_tools = model.bind_tools(tools)  # Same pattern!
```

**Key Compatibility Notes:**
- `bind_tools()` works identically to Gemini
- Tool call format is compatible with existing `should_continue()` routing
- Extended thinking can be enabled via `thinking` parameter

**Source:** [LangChain Anthropic Tool Use](https://python.langchain.com/api_reference/anthropic/chat_models/langchain_anthropic.chat_models.ChatAnthropic.html)

---

## AI SDK Frontend Integration

### Current Frontend Pattern (unchanged)
```typescript
// frontend-nuxt/server/api/chats/[id].post.ts
// This proxies to backend - no changes needed
const response = await fetch(`${backendUrl}/api/chat/aisdk`, {
  method: 'POST',
  body: JSON.stringify({ messages, chatId, model })
})
```

### Backend AI SDK Streaming (already compatible)
The backend's `/api/chat/aisdk` endpoint uses Vercel AI SDK Data Stream Protocol, which is model-agnostic. Claude responses will stream correctly.

---

## Dependencies to Install

### Backend (Python)
```bash
pip install langchain-anthropic>=0.3.14
```

### Frontend (optional - for direct Claude access)
```bash
npm install @ai-sdk/anthropic
```

---

## Environment Variables

```env
# .env (add to existing)
ANTHROPIC_API_KEY=sk-ant-api03-...

# Optional: for specific model override
CLAUDE_MODEL=claude-opus-4-5-20250514
CLAUDE_FALLBACK_MODEL=gemini-3-flash-preview
```

---

## Comparison: Claude Code SDK vs Direct API

| Feature | Claude Code SDK | Direct Anthropic API |
|---------|-----------------|---------------------|
| Integration complexity | High (subprocess) | Low (drop-in) |
| Tool compatibility | MCP-based (incompatible) | LangChain tools (compatible) |
| Streaming | Via events | Native AI SDK protocol |
| Latency | Higher (subprocess) | Lower (direct HTTP) |
| Customization | Limited | Full control |
| Cost | Same API pricing | Same API pricing |

**Verdict**: Direct API integration is simpler, faster, and fully compatible with our existing architecture.

---

## References

1. [Claude API Integration Guide 2025](https://collabnix.com/claude-api-integration-guide-2025-complete-developer-tutorial-with-code-examples/)
2. [AI Framework Comparison 2025: OpenAI Agents SDK vs Claude vs LangGraph](https://enhancial.substack.com/p/choosing-the-right-ai-framework-a)
3. [Building agents with Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
4. [LangChain + Claude Multi-Tool Agent Tutorial](https://www.marktechpost.com/2025/05/24/step-by-step-guide-to-build-a-customizable-multi-tool-ai-agent-with-langgraph-and-claude-for-dynamic-agent-creation/)
5. [Anthropic API Rate Limits: How to Handle 429 Errors](https://markaicode.com/anthropic-api-rate-limits-429-errors/)

---

# Implementation Plan

## Phase 1: Backend Claude Integration

### Step 1.1: Add Anthropic Dependencies
**File:** `backend/requirements.txt`

Add:
```
langchain-anthropic>=0.3.14
```

### Step 1.2: Create ChatAnthropicWithFallback Wrapper
**File:** `backend/models.py`

Create a new model wrapper class that:
1. Tries Claude (Opus 4.5 by default, Sonnet 4.5 as option)
2. Catches rate limit errors (429) and server overload (529)
3. Falls back to Gemini 3 Flash on failure
4. Logs fallback events for monitoring

```python
class ChatAnthropicWithFallback(BaseChatModel):
    """Claude model with automatic Gemini fallback on rate limits."""

    claude_model: ChatAnthropic
    gemini_fallback: ChatGoogleGenerativeAIWithKeyRotation

    def __init__(self, claude_model_name: str, gemini_fallback_name: str, ...):
        # Initialize both models
        # Store bound tools for re-binding on fallback
        pass

    async def _agenerate(self, messages, ...):
        try:
            return await self.claude_model._agenerate(messages, ...)
        except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
            if self._is_retriable(e):
                logger.warning(f"Claude rate limited, falling back to Gemini")
                return await self.gemini_fallback._agenerate(messages, ...)
            raise
```

### Step 1.3: Update Model Configuration
**File:** `backend/server.py`

Update `AVAILABLE_MODELS` to include Claude models:
```python
AVAILABLE_MODELS = [
    "claude-opus-4-5",      # Claude Opus 4.5 (default)
    "claude-sonnet-4-5",    # Claude Sonnet 4.5
    "gemini-3-flash-preview",
    "gemini-flash-latest",
]
DEFAULT_MODEL = "claude-opus-4-5"
```

### Step 1.4: Update get_chat_model Function
**File:** `backend/models.py`

Add Claude provider handling:
```python
def get_chat_model(provider=None, model_name=None, ...):
    # Detect if Claude model requested
    if model_name and model_name.startswith("claude-"):
        return ChatAnthropicWithFallback(
            claude_model_name=model_name,
            gemini_fallback_name="gemini-3-flash-preview"
        )
    # Existing Gemini logic...
```

---

## Phase 2: Frontend Model Selection

### Step 2.1: Update Model Configs
**File:** `frontend-nuxt/app/composables/useModels.ts`

Add Claude models to the selection:
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
  // Keep existing Gemini models as fallback options
  {
    id: 'gemini-3-flash-preview',
    displayName: 'Lab Assistant (Gemini 3 Flash)',
    icon: 'i-lucide-flask-conical',
    isLabAssistant: true
  },
]
```

### Step 2.2: Update Telegram Bot Models
**File:** `telegram_bot/keyboards/inline.py`

Update `AVAILABLE_MODELS`:
```python
AVAILABLE_MODELS = {
    "claude-opus-4-5": "🧠 Claude Opus 4.5 (más inteligente)",
    "claude-sonnet-4-5": "⚡ Claude Sonnet 4.5 (rápido)",
    "gemini-3-flash-preview": "🔬 Gemini 3 Flash (respaldo)",
}
DEFAULT_MODEL = "claude-opus-4-5"
```

---

## Phase 3: Extended Thinking Support (Optional)

### Step 3.1: Add Thinking Parameter
**File:** `backend/models.py`

For Claude models, support extended thinking:
```python
model_kwargs = {
    "model": model_name,
    "api_key": api_key,
    "temperature": 0.7,
}

# Enable extended thinking for complex reasoning
if enable_thinking:
    model_kwargs["thinking"] = {
        "type": "enabled",
        "budget_tokens": 8000  # Configurable
    }
```

### Step 3.2: Parse Thinking Blocks in Stream
**File:** `backend/server.py`

The existing reasoning parsing should work - Claude returns thinking in `thinking` content blocks similar to Gemini's approach.

---

## Phase 4: Environment & Testing

### Step 4.1: Update Environment Files
**Files:** `.env.example`, `README.md`

Add documentation for Anthropic API key:
```env
# Claude Configuration (Optional - falls back to Gemini if not set)
ANTHROPIC_API_KEY=sk-ant-api03-...
CLAUDE_MODEL=claude-opus-4-5  # or claude-sonnet-4-5
```

### Step 4.2: Create Test Script
**File:** `backend/test_claude.py`

Simple test to verify Claude integration:
```python
async def test_claude_integration():
    model = get_chat_model(model_name="claude-opus-4-5")
    response = await model.ainvoke([
        HumanMessage(content="Say 'Claude integration working!'")
    ])
    print(response.content)
```

---

## Implementation Priority

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Add `langchain-anthropic` dependency | 5 min | Required |
| 2 | Create `ChatAnthropicWithFallback` wrapper | 2 hours | Core feature |
| 3 | Update `get_chat_model()` for Claude | 30 min | Core feature |
| 4 | Update frontend model configs | 15 min | UX |
| 5 | Update Telegram bot models | 15 min | UX |
| 6 | Add ANTHROPIC_API_KEY to env | 5 min | Required |
| 7 | Test integration end-to-end | 1 hour | Verification |

**Total Estimated Effort: ~4-5 hours**

---

## Notes

1. **Image rotation stays with Gemini** - Fast, cheap, already working
2. **No frontend changes needed for streaming** - Backend handles everything
3. **Fallback is automatic** - Users won't notice rate limit hits
4. **Extended thinking** - Can be enabled per-model or per-request
5. **Cost consideration** - Claude Opus 4.5 is more expensive than Gemini; Sonnet 4.5 is a good balance
