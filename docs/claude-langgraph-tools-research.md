# Claude Agent SDK + LangGraph Tools Research

**Date:** January 2026
**Status:** Research Complete
**Issue:** Claude Code uses built-in tools (Bash, AskUserQuestion) instead of custom lab tools

---

## Executive Summary

**Question:** Can Claude Agent SDK use LangGraph tools directly?

**Answer:** **NO** - Claude Agent SDK cannot directly use LangGraph tools. They are different ecosystems with different tool formats.

**Solutions Available:**

| Option | Effort | Description |
|--------|--------|-------------|
| A. Adapter Library | Low | Use `langchain-tool-to-mcp-adapter` to convert existing tools |
| B. Dual Tools | Medium | Maintain LangGraph tools for Gemini, create MCP tools for Claude |
| C. MCP-Only | High | Convert everything to MCP, use `langchain-mcp-adapters` for Gemini |

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Lab AI Assistant                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  backend/graph/tools.py                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  from langchain_core.tools import tool                   │    │
│  │                                                          │    │
│  │  @tool                                                   │    │
│  │  async def create_new_order(cedula: str, exams: List):   │    │
│  │      ...                                                 │    │
│  │                                                          │    │
│  │  ALL_TOOLS = [search_orders, get_order_results, ...]    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                      │
│              ┌────────────┴────────────┐                        │
│              │                         │                        │
│              ▼                         ▼                        │
│  ┌───────────────────┐     ┌───────────────────┐               │
│  │   LangGraph       │     │  Claude Agent SDK │               │
│  │   (Gemini)        │     │  (Claude)         │               │
│  │   ✅ Works        │     │  ❌ Built-in only │               │
│  └───────────────────┘     └───────────────────┘               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why Claude Uses Built-in Tools Instead of Lab Tools

### Root Cause: `query()` vs `ClaudeSDKClient`

The current `claude_provider.py` uses:

```python
async for message in query(prompt=prompt, options=options):
```

**Problem:** The `query()` function is a lightweight API that:
- ❌ Does NOT support custom tools
- ❌ Does NOT support hooks
- ❌ Does NOT support sessions/memory

**Solution:** Must switch to `ClaudeSDKClient`:
- ✅ Supports custom MCP tools
- ✅ Supports hooks
- ✅ Supports conversation sessions

### Official Documentation Comparison

| Feature | `query()` | `ClaudeSDKClient` |
|---------|-----------|-------------------|
| Custom Tools | ❌ No | ✅ Yes (MCP format) |
| Hooks | ❌ No | ✅ Yes |
| Sessions | ❌ No | ✅ Yes |
| Memory | ❌ No | ✅ Yes |
| Use Case | One-off questions | Interactive applications |

---

## Tool Format Differences

### LangGraph/LangChain Format (Current)

```python
from langchain_core.tools import tool

@tool
async def create_new_order(cedula: str, exams: List[str]) -> str:
    """Create order. cedula="" for cotización. exams=["BH","EMO"]"""
    result = await _create_order_impl(cedula, exams)
    return json.dumps(result, ensure_ascii=False)
```

### Claude Agent SDK MCP Format (Required)

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("create_new_order", "Create order. cedula='' for cotización", {
    "cedula": str,
    "exams": list
})
async def create_new_order(args: dict) -> dict:
    result = await _create_order_impl(args["cedula"], args["exams"])
    return {"content": [{"type": "text", "text": json.dumps(result)}]}

# Bundle into MCP server
lab_server = create_sdk_mcp_server(
    name="lab-tools",
    version="1.0.0",
    tools=[create_new_order, edit_results, ...]
)
```

### Key Differences

| Aspect | LangGraph | Claude MCP |
|--------|-----------|------------|
| Decorator | `@tool` from langchain | `@tool(name, desc, schema)` from claude_agent_sdk |
| Arguments | Function parameters | Single `args: dict` |
| Return | String | `{"content": [{"type": "text", "text": "..."}]}` |
| Schema | Inferred or Pydantic | Dict or JSON Schema |

---

## Solution Options

### Option A: Use Adapter Library (Recommended)

**Package:** `langchain-tool-to-mcp-adapter`
**PyPI:** https://pypi.org/project/langchain-tool-to-mcp-adapter/

This converts LangChain tools to MCP format with minimal code changes:

```python
from mcp.server import FastMCP
from langchain_tool_to_mcp_adapter import add_langchain_tool_to_server
from graph.tools import ALL_TOOLS

# Create MCP server
server = FastMCP("lab-assistant")

# Convert all LangGraph tools to MCP
for tool in ALL_TOOLS:
    add_langchain_tool_to_server(server, tool)

# Use with Claude
options = ClaudeAgentOptions(
    mcp_servers={"lab": server},
    allowed_tools=[
        "mcp__lab__create_new_order",
        "mcp__lab__edit_results",
        "mcp__lab__search_orders",
        # ...
    ]
)
```

**Pros:**
- Minimal code changes
- Reuse existing tools
- Keep Gemini working as-is

**Cons:**
- Additional dependency
- Beta status package
- May have edge cases with complex types

---

### Option B: Dual Tool Definitions

Maintain separate tool files:

```
backend/
├── graph/
│   └── tools.py           # LangGraph tools (for Gemini)
├── mcp/
│   └── tools.py           # MCP tools (for Claude)
└── tools_core.py          # Shared implementation logic
```

**Pros:**
- Full control over each format
- No adapter dependencies
- Optimal for each framework

**Cons:**
- Code duplication
- Maintenance overhead
- Must keep both in sync

---

### Option C: MCP-Only Architecture

Convert everything to MCP, use `langchain-mcp-adapters` for Gemini:

```python
# Define tools in MCP format (primary)
from claude_agent_sdk import tool

@tool("create_new_order", "Create order", {"cedula": str, "exams": list})
async def create_new_order(args):
    ...

# For Gemini, convert MCP → LangChain
from langchain_mcp_adapters.tools import load_mcp_tools
langchain_tools = await load_mcp_tools(mcp_session)
```

**Pros:**
- Single source of truth
- MCP is industry standard (adopted by OpenAI, Anthropic)
- Future-proof

**Cons:**
- Major refactor required
- LangGraph adapter less mature
- Risk breaking Gemini

---

## Disabling Claude's Built-in Tools

Three methods available:

### Method 1: Whitelist (Recommended)

Only list your custom tools - anything not listed is disabled:

```python
ClaudeAgentOptions(
    mcp_servers={"lab": lab_server},
    allowed_tools=[
        "mcp__lab__create_new_order",
        "mcp__lab__edit_results",
        # Only these tools are available - Bash, Read, etc. are disabled
    ]
)
```

### Method 2: Blocklist

Explicitly block specific tools:

```python
ClaudeAgentOptions(
    disallowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch"]
)
```

### Method 3: Permission Deny Rules

In `.claude/settings.json`:

```json
{
  "permissions": {
    "deny": ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
  }
}
```

---

## Implementation Plan (Option A)

### Step 1: Install Adapter

```bash
pip install langchain-tool-to-mcp-adapter
```

### Step 2: Create MCP Wrapper

```python
# backend/claude_mcp_tools.py
from mcp.server import FastMCP
from langchain_tool_to_mcp_adapter import add_langchain_tool_to_server
from graph.tools import ALL_TOOLS

def create_lab_mcp_server():
    """Create MCP server with all lab tools."""
    server = FastMCP("lab-assistant")

    for tool in ALL_TOOLS:
        add_langchain_tool_to_server(server, tool)

    return server
```

### Step 3: Update Claude Provider

```python
# backend/claude_provider.py
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_mcp_tools import create_lab_mcp_server

class ClaudeCodeProvider:
    def __init__(self):
        self.mcp_server = create_lab_mcp_server()

    async def chat_stream(self, prompt: str, ...):
        options = ClaudeAgentOptions(
            mcp_servers={"lab": self.mcp_server},
            allowed_tools=[
                "mcp__lab__search_orders",
                "mcp__lab__get_order_results",
                "mcp__lab__get_order_info",
                "mcp__lab__edit_results",
                "mcp__lab__edit_order_exams",
                "mcp__lab__create_new_order",
                "mcp__lab__ask_user",
                "mcp__lab__get_available_exams",
            ],
            # Disable ALL built-in tools by not listing them
        )

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                yield message
```

---

## Related GitHub Issues

| Issue | Status | Description |
|-------|--------|-------------|
| [#1380](https://github.com/anthropics/claude-code/issues/1380) | ✅ Closed | Disable native tools - solved via permissions |
| [#7328](https://github.com/anthropics/claude-code/issues/7328) | Open | MCP tool filtering |

---

## MCP Industry Adoption (2025-2026)

- **December 2025:** Anthropic donated MCP to Linux Foundation's Agentic AI Foundation
- **March 2025:** OpenAI adopted MCP across products
- **Co-founders:** Anthropic, Block, OpenAI
- **Supporters:** Google, Microsoft, AWS, Cloudflare, Bloomberg

MCP is becoming the industry standard for AI tool integration.

---

## Recommendations

### For Your Use Case

**Recommended: Option A (Adapter Library)**

1. Keep LangGraph for Gemini (works perfectly)
2. Use `langchain-tool-to-mcp-adapter` to convert tools for Claude
3. Use `ClaudeSDKClient` instead of `query()`
4. Whitelist only your MCP tools (disables Bash, etc.)

### Why Not Option B or C?

- **Option B (Dual):** Too much maintenance for 8 tools
- **Option C (MCP-only):** Risk breaking working Gemini integration

---

## Sources

- [Claude Agent SDK Custom Tools](https://platform.claude.com/docs/en/agent-sdk/custom-tools)
- [Claude Agent SDK Python Reference](https://platform.claude.com/docs/en/agent-sdk/python)
- [langchain-tool-to-mcp-adapter (PyPI)](https://pypi.org/project/langchain-tool-to-mcp-adapter/)
- [langchain-mcp-adapters (GitHub)](https://github.com/langchain-ai/langchain-mcp-adapters)
- [GitHub Issue #1380: Disable Native Tools](https://github.com/anthropics/claude-code/issues/1380)
- [Anthropic Engineering: Building Agents](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
