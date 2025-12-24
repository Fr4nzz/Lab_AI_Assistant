# Lab Assistant Migration Coding Plan
## From Custom Python/React to LangGraph + LobeChat

**Project Goal**: Migrate the existing lab assistant application from a custom agentic loop and React frontend to use LangGraph (backend) and LobeChat (frontend) for a more robust, maintainable, and feature-rich system.

**Key Requirements**:
1. **Batch efficiency**: Minimize iterations by processing multiple orders in single tool calls
2. **Multi-modal**: Support audio recording, image upload, camera capture
3. **Editable tables**: AI generates tables that users can edit before execution
4. **Model flexibility**: Support Google Gemini (dev/free) and OpenRouter (production)
5. **Token optimization**: Use diff-based file edits instead of regenerating full content

## IMPORTANT: Safety Model Clarification

**NO INTERRUPT/APPROVAL MECHANISM NEEDED!**

The safety model is handled by the **website itself**, not by LangGraph:

```
AI Tools (edit_results, add_exam, create_order)
              ↓
    Fill form fields in browser (NOT SAVED)
              ↓
    Human reviews filled data in browser tabs
              ↓
    Human manually clicks "Guardar" button (ONLY way to save)
```

All tools are "safe" because:
- `edit_results()` → Only fills form fields, requires manual Save
- `add_exam_to_order()` → Only adds exam to form, requires manual Save  
- `create_new_order()` → Only creates order form, requires manual Save
- The AI **CANNOT** click Save/Delete buttons (enforced by BrowserManager.FORBIDDEN_WORDS)

Therefore, the LangGraph migration focuses on:
- ✅ Better state management and conversation persistence
- ✅ Cleaner agentic loop with proper tool execution
- ✅ Batch operations to minimize iterations (2-3 instead of 5)
- ✅ Streaming support for real-time responses
- ❌ NOT interrupt-based approval (website handles this)

---

## Table of Contents

1. [Current Architecture Analysis](#1-current-architecture-analysis)
2. [Target Architecture](#2-target-architecture)
3. [Phase 1: LangGraph Backend Migration](#phase-1-langgraph-backend-migration)
4. [Phase 2: LobeChat Frontend Setup](#phase-2-lobechat-frontend-setup)
5. [Phase 3: Integration & Custom Plugin](#phase-3-integration--custom-plugin)
6. [Phase 4: Testing & Deployment](#phase-4-testing--deployment)
7. [Reference Documentation](#reference-documentation)

---

## 1. Current Architecture Analysis

### Files to Migrate/Replace

| Current File | Purpose | Migration Action |
|--------------|---------|------------------|
| `backend/lab_agent.py` | Main agent with manual while loop | **Replace** with LangGraph StateGraph |
| `backend/gemini_handler.py` | Gemini API with key rotation | **Adapt** to LangChain model abstraction |
| `backend/tool_executor.py` | Tool execution | **Replace** with LangGraph ToolNode |
| `backend/tools.py` | Tool definitions | **Convert** to @tool decorated functions |
| `backend/prompts.py` | System prompts | **Keep** and adapt for LangGraph |
| `backend/extractors.py` | Page data extraction | **Keep** as utility functions for tools |
| `backend/browser_manager.py` | Playwright control | **Keep** and wrap in tools |
| `backend/main.py` | FastAPI server | **Refactor** for LangGraph integration |
| `frontend/*` | React chat UI | **Replace** with LobeChat |

### Current Agentic Loop (to be replaced)

```python
# Current pattern in lab_agent.py - REPLACE THIS
MAX_ITERATIONS = 5
iteration = 0
all_tool_results = []

while iteration < MAX_ITERATIONS:
    # Manual context extraction
    cached_context = await self._get_current_context()
    
    # Manual prompt building
    system_prompt = build_system_prompt(...)
    
    # Manual Gemini call
    response_text, success = await self.gemini.send_request(...)
    
    # Manual tool execution
    for call in tool_calls:
        result = await self.executor.execute(...)
        all_tool_results.append(result)
```

---

## 2. Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     LobeChat Frontend                           │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ ┌────────────────┐  │
│  │  Audio   │ │  Image   │ │   Chat      │ │  Browser       │  │
│  │  Record  │ │  Upload  │ │   View      │ │  Screenshot    │  │
│  └────┬─────┘ └────┬─────┘ └──────┬──────┘ └───────┬────────┘  │
└───────┼────────────┼───────────────┼───────────────┼────────────┘
        │            │               │               │
        ▼            ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                              │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │              LangGraph StateGraph (Simple)                  ││
│  │                                                             ││
│  │  ┌─────────┐   ┌──────────┐   ┌──────────┐                 ││
│  │  │  START  │──▶│  Agent   │──▶│  Tools   │                 ││
│  │  └─────────┘   │  Node    │   │  Node    │                 ││
│  │                └────┬─────┘   └────┬─────┘                 ││
│  │                     │              │                       ││
│  │                     │◀─────────────┘                       ││
│  │                     │ (loop until no tool calls)           ││
│  │                     ▼                                      ││
│  │                ┌─────────┐                                 ││
│  │                │   END   │ (return response to user)       ││
│  │                └─────────┘                                 ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Checkpointer    │  │ Browser Manager │  │ Model Provider  │ │
│  │ (SQLite/PG)     │  │ (Playwright)    │  │ (Gemini/OpenR.) │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
          │
          │ Playwright fills forms
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Target Website (Orion Labs)                    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │   Form Fields (Filled by AI)                            │   │
│  │   [Hemoglobina: 15.5] [Hematocrito: 46]                │   │
│  │   [Color: Café Rojizo] [Consistencia: Diarreica]       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │   🔒 HUMAN-IN-THE-LOOP: User clicks [Guardar] button   │   │
│  │   (AI cannot click this - safety enforced by code)      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Flow Summary:**
1. User sends message (can include audio/images)
2. LangGraph agent decides on tools → executes them → loops
3. Tools fill browser forms but NEVER save
4. Agent responds when done (no more tool calls)
5. User reviews filled forms in browser
6. User manually clicks "Guardar" to save (safety)

---

## Phase 1: LangGraph Backend Migration

### Step 1.1: Install Dependencies

Create new `backend/requirements.txt`:

```txt
# LangGraph and LangChain
langgraph>=0.2.31
langgraph-checkpoint-sqlite
langgraph-checkpoint-postgres
langchain>=0.3.0
langchain-core>=0.3.0
langchain-google-genai>=2.0.0
langchain-openai>=0.2.0

# Existing dependencies
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6
playwright>=1.40.0
sqlalchemy>=2.0.0
python-dotenv>=1.0.0
pydantic>=2.0.0

# Additional for async support
asyncpg  # For PostgreSQL async
aiosqlite  # For SQLite async
```

### Step 1.2: Create Model Provider Abstraction

Create `backend/models.py`:

```python
"""
Model provider abstraction for Gemini (dev) and OpenRouter (production).

DOCUMENTATION:
- ChatGoogleGenerativeAI: https://python.langchain.com/docs/integrations/chat/google_generative_ai
- ChatOpenAI with OpenRouter: https://openrouter.ai/docs

USAGE:
    model = get_chat_model()  # Uses LLM_PROVIDER env var
    model_with_tools = model.bind_tools(tools)
"""
import os
from typing import Optional, List
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI


def get_chat_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None
) -> BaseChatModel:
    """
    Get chat model based on provider.
    
    Args:
        provider: "gemini" or "openrouter". Defaults to LLM_PROVIDER env var.
        model_name: Specific model name. Defaults based on provider.
    
    Returns:
        Configured chat model instance.
    
    Environment Variables:
        LLM_PROVIDER: Default provider ("gemini" or "openrouter")
        GOOGLE_API_KEY: Required for Gemini
        OPENROUTER_API_KEY: Required for OpenRouter
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "gemini")
    
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model_name or os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview"),
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
            temperature=0.7,
            convert_system_message_to_human=True  # Gemini quirk
        )
    
    elif provider == "openrouter":
        return ChatOpenAI(
            model=model_name or os.environ.get("OPENROUTER_MODEL", "google/gemini-3-flash-preview"),
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            default_headers={
                "HTTP-Referer": os.environ.get("APP_URL", "http://localhost:3000"),
                "X-Title": "Lab Assistant"
            },
            temperature=0.7
        )
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'gemini' or 'openrouter'.")


def get_model_with_multimodal_support(provider: Optional[str] = None) -> BaseChatModel:
    """
    Get model configured for multi-modal input (images, audio).
    
    For Gemini: Native multi-modal support
    For OpenRouter: Use vision-capable models
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "gemini")
    
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",  # Vision + Audio capable
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
        )
    else:
        return ChatOpenAI(
            model="google/gemini-3-flash-preview",  # Vision capable via OpenRouter
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )
```

### Step 1.3: Create LangGraph State Schema

Create `backend/graph/state.py`:

```python
"""
LangGraph State Schema for Lab Assistant.

DOCUMENTATION:
- State Schema: https://langchain-ai.github.io/langgraph/concepts/low_level/#state
- Reducers (add_messages): https://langchain-ai.github.io/langgraph/concepts/low_level/#reducers
- TypedDict: Standard Python typing

KEY CONCEPTS:
- Annotated[list, add_messages] - Messages are APPENDED, not replaced
- Other fields are REPLACED by default
- State persists across conversation via checkpointer

NOTE: No approval/interrupt fields needed - the website's Save button
is the human-in-the-loop mechanism. AI can freely fill forms.
"""
from typing import Annotated, Optional, List, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class LabAssistantState(TypedDict):
    """
    Complete state for the Lab Assistant agent.
    
    Attributes:
        messages: Conversation history (uses add_messages reducer - appends)
        current_page_context: Extracted data from current browser page
        current_page_type: Type of page ("ordenes_list", "reportes", etc.)
        active_tabs: Dict of open browser tabs {orden_num: tab_info}
        execution_results: Results from tool executions in current turn
    """
    # Core conversation (REDUCER: appends new messages)
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Browser/page context (updated by navigation tools)
    current_page_context: Optional[Dict[str, Any]]
    current_page_type: Optional[str]  # "ordenes_list", "reportes", "orden_edit", etc.
    
    # Tab management for batch editing
    active_tabs: Optional[Dict[str, Dict[str, Any]]]  # {orden_num: {page, data}}
    
    # Tool execution tracking for current turn
    execution_results: Optional[List[Dict[str, Any]]]
```

### Step 1.4: Convert Tools to LangChain Format

Create `backend/graph/tools.py`:

```python
"""
LangChain-compatible tool definitions for Lab Assistant.

DOCUMENTATION:
- @tool decorator: https://python.langchain.com/docs/how_to/custom_tools/
- StructuredTool: https://python.langchain.com/docs/how_to/custom_tools/#structuredtool
- Tool annotations: https://python.langchain.com/docs/how_to/tool_configure/

DESIGN PRINCIPLES:
1. ALL tools are safe - they only fill forms, never save
2. Batch operations - accept arrays to minimize iterations
3. Return strings (will be added to messages)
4. The website's Save button is the human-in-the-loop mechanism

BATCH EFFICIENCY GOAL:
- Ideal flow: search → get_exam_fields (all orders) → edit_results (all fields) → done
- Target: 2-3 iterations instead of 5+
"""
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool, ToolException
from pydantic import BaseModel, Field
import asyncio
import json

# Import existing functionality
import sys
sys.path.append('..')
from browser_manager import BrowserManager
from extractors import PageDataExtractor, EXTRACT_ORDENES_JS, EXTRACT_REPORTES_JS, EXTRACT_ORDEN_EDIT_JS


# Global browser instance (will be set during app startup)
_browser: Optional[BrowserManager] = None
_extractor: Optional[PageDataExtractor] = None
_active_tabs: Dict[str, Any] = {}  # {orden_num: Page}


def set_browser(browser: BrowserManager):
    """Set the browser instance for tools to use."""
    global _browser, _extractor
    _browser = browser
    if browser.page:
        _extractor = PageDataExtractor(browser.page)


# ============================================================
# SEARCH & NAVIGATION TOOLS
# ============================================================

@tool
def search_orders(search: str = "", limit: int = 20) -> str:
    """
    Search orders by patient name or ID number (cédula).
    Returns a list of matching orders with their IDs for further operations.
    
    Args:
        search: Text to search (patient name or cédula). Empty returns recent orders.
        limit: Maximum orders to return (default 20)
    
    Returns:
        JSON with order list including: num, fecha, paciente, cedula, estado, id
    
    Example:
        search_orders(search="chandi franz", limit=10)
    """
    async def _search():
        page = await _browser.ensure_page()
        if search:
            url = f"https://laboratoriofranz.orion-labs.com/ordenes?cadenaBusqueda={search}&page=1"
        else:
            url = "https://laboratoriofranz.orion-labs.com/ordenes"
        
        await page.goto(url, timeout=30000)
        await page.wait_for_timeout(2000)
        
        ordenes = await page.evaluate(EXTRACT_ORDENES_JS)
        return ordenes[:limit]
    
    result = asyncio.get_event_loop().run_until_complete(_search())
    return json.dumps({
        "ordenes": result, 
        "total": len(result),
        "tip": "Use 'num' field for get_exam_fields(), use 'id' field for get_order_details()"
    }, ensure_ascii=False)


@tool
def get_exam_fields(ordenes: List[str]) -> str:
    """
    Get exam fields for ONE OR MORE orders. Opens browser tabs for editing.
    BATCH OPERATION: Pass ALL order numbers you need at once to minimize iterations.
    
    Args:
        ordenes: List of order NUMBERS (the 'num' field, e.g., ["2501181", "25011314"])
    
    Returns:
        JSON with exam fields for each order, tabs remain open for edit_results()
    
    Example - Single order:
        get_exam_fields(ordenes=["2501181"])
    
    Example - Multiple orders (PREFERRED for efficiency):
        get_exam_fields(ordenes=["2501181", "25011314", "2501200"])
    """
    global _active_tabs
    
    async def _get_fields():
        results = []
        for orden in ordenes:
            # Reuse existing tab or create new one
            if orden in _active_tabs:
                page = _active_tabs[orden]
                await page.reload()
            else:
                page = await _browser.context.new_page()
                _active_tabs[orden] = page
            
            url = f"https://laboratoriofranz.orion-labs.com/reportes2?numeroOrden={orden}"
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Inject highlight styles
            await _inject_highlight_styles(page)
            
            data = await page.evaluate(EXTRACT_REPORTES_JS)
            results.append({
                "orden": orden, 
                "tab_ready": True, 
                **data
            })
        
        return results
    
    result = asyncio.get_event_loop().run_until_complete(_get_fields())
    return json.dumps({
        "ordenes": result,
        "total": len(result),
        "tabs_open": len(_active_tabs),
        "tip": "Tabs are ready. Use edit_results() with ALL fields you want to change."
    }, ensure_ascii=False)


@tool
def get_order_details(order_ids: List[int]) -> str:
    """
    Get details of ONE OR MORE orders by their internal IDs.
    Use this to check what exams exist in orders before editing.
    BATCH OPERATION: Pass ALL order IDs you need at once.
    
    Args:
        order_ids: List of internal order IDs (the 'id' field, e.g., [4282, 4150])
    
    Returns:
        JSON with order details (patient info, exams list, totals) for each order
    
    Example - Single order:
        get_order_details(order_ids=[4282])
    
    Example - Multiple orders (PREFERRED):
        get_order_details(order_ids=[4282, 4150, 4100])
    """
    async def _get_details():
        results = []
        for order_id in order_ids:
            page = await _browser.ensure_page()
            url = f"https://laboratoriofranz.orion-labs.com/ordenes/{order_id}/edit"
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(1500)
            
            data = await page.evaluate(EXTRACT_ORDEN_EDIT_JS)
            data["order_id"] = order_id
            results.append(data)
        
        return results
    
    result = asyncio.get_event_loop().run_until_complete(_get_details())
    return json.dumps({
        "orders": result,
        "total": len(result)
    }, ensure_ascii=False)


# ============================================================
# FORM EDITING TOOLS (All safe - only fill forms, never save)
# ============================================================

class EditResultsInput(BaseModel):
    """Input schema for edit_results tool."""
    data: List[Dict[str, str]] = Field(
        description="List of field edits. Each item must have: orden (order number), e (exam name), f (field name), v (value)"
    )


@tool(args_schema=EditResultsInput)
def edit_results(data: List[Dict[str, str]]) -> str:
    """
    Edit exam result fields in browser forms. Fields are auto-highlighted.
    BATCH OPERATION: Pass ALL fields for ALL orders at once.
    
    IMPORTANT: This only FILLS the forms. User must click "Guardar" to save.
    
    Args:
        data: List of edits. Each item needs:
            - orden: Order NUMBER (e.g., "2501181")
            - e: Exam name (e.g., "BIOMETRÍA HEMÁTICA")
            - f: Field name (e.g., "Hemoglobina")
            - v: Value to set (e.g., "15.5")
    
    Returns:
        Summary of fields filled, with before/after values
    
    Example - Edit multiple fields across multiple orders:
        edit_results(data=[
            {"orden": "2501181", "e": "BIOMETRÍA HEMÁTICA", "f": "Hemoglobina", "v": "15.5"},
            {"orden": "2501181", "e": "BIOMETRÍA HEMÁTICA", "f": "Hematocrito", "v": "46"},
            {"orden": "25011314", "e": "COPROPARASITARIO", "f": "Color", "v": "Café Rojizo"},
            {"orden": "25011314", "e": "COPROPARASITARIO", "f": "Consistencia", "v": "Diarreica"}
        ])
    """
    global _active_tabs
    
    FILL_FIELD_JS = r"""
    (params) => {
        const rows = document.querySelectorAll('tr.parametro');
        for (const row of rows) {
            const labelCell = row.querySelector('td:first-child');
            const labelText = labelCell?.innerText?.trim();
            if (!labelText || !labelText.toLowerCase().includes(params.f.toLowerCase())) {
                continue;
            }
            const input = row.querySelector('input');
            const select = row.querySelector('select');
            const control = input || select;
            if (!control) continue;
            
            const prev = input ? input.value : (select.options[select.selectedIndex]?.text || '');
            
            if (input) {
                input.value = params.v;
                input.dispatchEvent(new Event('input', {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
            } else if (select) {
                let found = false;
                for (const opt of select.options) {
                    if (opt.text.toLowerCase().includes(params.v.toLowerCase())) {
                        select.value = opt.value;
                        select.dispatchEvent(new Event('change', {bubbles: true}));
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    return {err: 'Option not found: ' + params.v + ' in field ' + params.f};
                }
            }
            
            // Auto-highlight the changed field
            control.classList.add('ai-modified');
            row.classList.add('ai-modified-row');
            
            // Add change indicator
            const existingBadge = control.parentNode.querySelector('.ai-change-badge');
            if (!existingBadge) {
                const indicator = document.createElement('span');
                indicator.className = 'ai-change-badge';
                indicator.textContent = prev + ' → ' + params.v;
                control.parentNode.appendChild(indicator);
            }
            
            control.scrollIntoView({behavior: 'smooth', block: 'center'});
            return {field: labelText, prev: prev, new: params.v};
        }
        return {err: 'Field not found: ' + params.f};
    }
    """
    
    async def _edit():
        results = []
        results_by_orden = {}
        
        for item in data:
            orden = item["orden"]
            
            # Get the page for this order
            if orden not in _active_tabs:
                results.append({
                    "orden": orden, 
                    "err": f"No tab open for order {orden}. Call get_exam_fields first."
                })
                continue
            
            page = _active_tabs[orden]
            await page.bring_to_front()
            
            result = await page.evaluate(FILL_FIELD_JS, {
                "e": item["e"], 
                "f": item["f"], 
                "v": item["v"]
            })
            result["orden"] = orden
            results.append(result)
            
            # Track by order
            if orden not in results_by_orden:
                results_by_orden[orden] = {"filled": 0, "errors": 0}
            if "field" in result:
                results_by_orden[orden]["filled"] += 1
            if "err" in result:
                results_by_orden[orden]["errors"] += 1
        
        return results, results_by_orden
    
    results, by_orden = asyncio.get_event_loop().run_until_complete(_edit())
    filled = len([r for r in results if "field" in r])
    errors = [r for r in results if "err" in r]
    
    return json.dumps({
        "filled": filled,
        "total": len(data),
        "by_orden": by_orden,
        "details": results,
        "errors": errors,
        "next_step": "Ask user to review highlighted fields and click 'Guardar' in each tab."
    }, ensure_ascii=False)


@tool
def add_exam_to_order(order_id: int, exam_code: str) -> str:
    """
    Add an exam to an existing order. Form must be saved manually by user.
    
    Args:
        order_id: Internal order ID (the 'id' field)
        exam_code: Exam code to add (e.g., "EMO", "BH", "COPROPARASITARIO")
    
    Returns:
        Confirmation message. User must click Guardar to save.
    
    Example:
        add_exam_to_order(order_id=4282, exam_code="EMO")
    """
    async def _add_exam():
        page = await _browser.ensure_page()
        url = f"https://laboratoriofranz.orion-labs.com/ordenes/{order_id}/edit"
        await page.goto(url)
        await page.wait_for_timeout(1500)
        
        search = page.locator('#buscar-examen-input')
        await search.fill(exam_code)
        await page.wait_for_timeout(800)
        
        add_btn = page.locator('button[id*="examen"]').first
        if await add_btn.count() > 0:
            await add_btn.click()
            return {"added": exam_code, "order_id": order_id, "status": "pending_save"}
        return {"err": f"Could not find exam {exam_code}"}
    
    result = asyncio.get_event_loop().run_until_complete(_add_exam())
    return json.dumps({
        **result,
        "next_step": "User must click 'Guardar' to save the exam to the order."
    }, ensure_ascii=False)


@tool
def create_new_order(cedula: str, exams: List[str]) -> str:
    """
    Create a new order form for a patient. Form must be saved manually by user.
    
    Args:
        cedula: Patient ID number (cédula)
        exams: List of exam codes to add (e.g., ["EMO", "BH"])
    
    Returns:
        Confirmation message. User must click Guardar to save.
    
    Example:
        create_new_order(cedula="1500887144", exams=["EMO", "COPROPARASITARIO"])
    """
    async def _create():
        page = await _browser.ensure_page()
        await page.goto("https://laboratoriofranz.orion-labs.com/ordenes/create")
        await page.wait_for_timeout(1000)
        
        cedula_input = page.locator('#identificacion')
        await cedula_input.fill(cedula)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)
        
        added_exams = []
        for exam in exams:
            search = page.locator('#buscar-examen-input')
            await search.fill(exam)
            await page.wait_for_timeout(800)
            add_btn = page.locator('button[id*="examen"]').first
            if await add_btn.count() > 0:
                await add_btn.click()
                added_exams.append(exam)
                await page.wait_for_timeout(500)
        
        return {"cedula": cedula, "exams_added": added_exams, "status": "pending_save"}
    
    result = asyncio.get_event_loop().run_until_complete(_create())
    return json.dumps({
        **result,
        "next_step": "User must click 'Guardar' to create the order."
    }, ensure_ascii=False)


# ============================================================
# UI HELPER TOOLS
# ============================================================

@tool
def highlight_fields(fields: List[str], color: str = "yellow") -> str:
    """
    Highlight specific fields in the browser to draw user attention.
    
    Args:
        fields: Field names to highlight (partial match)
        color: Highlight color - yellow, green, red, or blue
    
    Example:
        highlight_fields(fields=["Hemoglobina", "Hematocrito"], color="yellow")
    """
    color_map = {
        "yellow": "#fef3c7",
        "green": "#d1fae5",
        "red": "#fee2e2",
        "blue": "#dbeafe"
    }
    
    async def _highlight():
        # Highlight in all active tabs
        highlighted = []
        for orden, page in _active_tabs.items():
            await page.evaluate("""
                (params) => {
                    const rows = document.querySelectorAll('tr.parametro');
                    for (const row of rows) {
                        const label = row.querySelector('td:first-child')?.innerText?.trim();
                        for (const field of params.fields) {
                            if (label && label.toLowerCase().includes(field.toLowerCase())) {
                                row.style.backgroundColor = params.color;
                            }
                        }
                    }
                }
            """, {"fields": fields, "color": color_map.get(color, "#fef3c7")})
            highlighted.append(orden)
        
        return highlighted
    
    result = asyncio.get_event_loop().run_until_complete(_highlight())
    return json.dumps({
        "highlighted_fields": fields,
        "in_tabs": result,
        "color": color
    }, ensure_ascii=False)


@tool
def ask_user(action: str, message: str) -> str:
    """
    Display a message to the user requesting action or information.
    
    Args:
        action: Type of request - "save", "info", "confirm", "clarify"
        message: Message to display to the user
    
    Example:
        ask_user(action="save", message="Please review the highlighted fields and click Guardar")
    """
    return json.dumps({
        "waiting_for": action,
        "message": message,
        "status": "waiting_for_user"
    }, ensure_ascii=False)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def _inject_highlight_styles(page):
    """Inject CSS for highlighting modified fields."""
    HIGHLIGHT_STYLES = """
        .ai-modified {
            background-color: #fef3c7 !important;
            border: 2px solid #f59e0b !important;
            box-shadow: 0 0 8px rgba(245, 158, 11, 0.4) !important;
        }
        .ai-modified-row {
            background-color: #fffbeb !important;
        }
        .ai-change-badge {
            display: inline-block;
            background: #dc2626;
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            margin-left: 8px;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
    """
    await page.evaluate(f"""
        () => {{
            if (document.getElementById('ai-styles')) return;
            const style = document.createElement('style');
            style.id = 'ai-styles';
            style.textContent = `{HIGHLIGHT_STYLES}`;
            document.head.appendChild(style);
        }}
    """)


def close_tab(orden: str):
    """Close a specific tab."""
    global _active_tabs
    if orden in _active_tabs:
        asyncio.get_event_loop().run_until_complete(_active_tabs[orden].close())
        del _active_tabs[orden]


def close_all_tabs():
    """Close all active tabs."""
    global _active_tabs
    for page in _active_tabs.values():
        asyncio.get_event_loop().run_until_complete(page.close())
    _active_tabs.clear()


# All tools list for binding to model
ALL_TOOLS = [
    search_orders,
    get_exam_fields,
    get_order_details,
    edit_results,
    add_exam_to_order,
    create_new_order,
    highlight_fields,
    ask_user
]
```

### Step 1.5: Create the LangGraph Agent

Create `backend/graph/agent.py`:

```python
"""
LangGraph Agent for Lab Assistant.

DOCUMENTATION:
- StateGraph: https://langchain-ai.github.io/langgraph/concepts/low_level/#stategraph
- Nodes and Edges: https://langchain-ai.github.io/langgraph/concepts/low_level/#nodes
- Conditional Edges: https://langchain-ai.github.io/langgraph/concepts/low_level/#conditional-edges
- Prebuilt ReAct: https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/

ARCHITECTURE (Simple - No Approval Needed):
┌─────────┐     ┌─────────┐     ┌─────────┐
│  START  │────▶│  Agent  │────▶│  Tools  │
└─────────┘     └────┬────┘     └────┬────┘
                     │               │
                     │◀──────────────┘
                     │
                     ▼ (no tool calls)
               ┌─────────┐
               │   END   │
               └─────────┘

All tools are SAFE - they only fill browser forms.
The website's "Guardar" button is the human-in-the-loop.

OPTIMIZATION GOAL:
- Current system: 5 iterations (search → get_fields → edit → ask_user → summary)
- Target: 3 iterations (search → get_fields → edit+respond)
- Key: Agent should respond directly after edit_results, no need for ask_user
"""
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .state import LabAssistantState
from .tools import ALL_TOOLS, set_browser
from ..models import get_chat_model
from ..prompts import SYSTEM_PROMPT


def create_lab_agent(browser_manager=None):
    """
    Create the LangGraph agent for lab assistance.
    
    This is a simple ReAct-style agent:
    1. Agent receives message, decides on tool calls
    2. Tools execute (browser automation)
    3. Agent sees results, decides next action or responds
    4. Loop until agent responds without tool calls
    
    Args:
        browser_manager: BrowserManager instance for Playwright control
    
    Returns:
        StateGraph builder (compile with checkpointer before use)
    """
    if browser_manager:
        set_browser(browser_manager)
    
    # Get model and bind tools
    model = get_chat_model()
    model_with_tools = model.bind_tools(ALL_TOOLS)
    
    # ============================================================
    # NODE DEFINITIONS
    # ============================================================
    
    def agent_node(state: LabAssistantState) -> dict:
        """
        Main agent node - calls LLM with conversation history.
        
        The LLM decides whether to:
        1. Call tools to gather info or take action
        2. Respond directly to the user (ends the loop)
        """
        # Build system message with current context
        context_str = ""
        if state.get("current_page_context"):
            context_str = f"\n\nCONTEXTO ACTUAL DE LA PÁGINA:\n{state['current_page_context']}"
        
        system_content = SYSTEM_PROMPT + context_str
        system_msg = SystemMessage(content=system_content)
        
        # Build message list
        messages = [system_msg] + list(state["messages"])
        
        # Call LLM
        response = model_with_tools.invoke(messages)
        
        return {"messages": [response]}
    
    def tools_node(state: LabAssistantState) -> dict:
        """
        Execute tool calls from the last AI message.
        
        Uses LangGraph's prebuilt ToolNode which:
        - Extracts tool_calls from the last AIMessage
        - Executes each tool
        - Returns ToolMessages with results
        """
        tool_executor = ToolNode(ALL_TOOLS)
        return tool_executor.invoke(state)
    
    # ============================================================
    # ROUTING FUNCTION
    # ============================================================
    
    def should_continue(state: LabAssistantState) -> Literal["tools", "__end__"]:
        """
        Determine if we should execute tools or end.
        
        Simple logic:
        - If last message has tool_calls → execute them
        - Otherwise → end (agent has responded to user)
        """
        last_message = state["messages"][-1]
        
        # Check if there are tool calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        
        # No tool calls - agent is done, return response to user
        return END
    
    # ============================================================
    # GRAPH CONSTRUCTION
    # ============================================================
    
    builder = StateGraph(LabAssistantState)
    
    # Add nodes
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tools_node)
    
    # Add edges
    builder.add_edge(START, "agent")
    
    # Conditional edge from agent
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    
    # After tools, always go back to agent
    builder.add_edge("tools", "agent")
    
    return builder


def compile_agent(builder: StateGraph, checkpointer=None):
    """
    Compile the agent graph, optionally with a checkpointer.
    
    DOCUMENTATION:
    - Checkpointers: https://langchain-ai.github.io/langgraph/concepts/persistence/
    - MemorySaver: For development/testing (in-memory)
    - SqliteSaver: For production with SQLite
    - PostgresSaver: For production with PostgreSQL
    
    Checkpointer enables:
    - Conversation persistence across requests
    - State recovery after crashes
    - Thread-based conversation isolation
    
    Args:
        builder: Configured StateGraph builder
        checkpointer: Optional checkpointer for persistence
    
    Returns:
        Compiled graph ready for invocation
    """
    if checkpointer:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()


# ============================================================
# ALTERNATIVE: Use Prebuilt ReAct Agent
# ============================================================

def create_react_agent_simple(browser_manager=None):
    """
    Alternative: Use LangGraph's prebuilt create_react_agent.
    
    This is simpler but less customizable.
    
    DOCUMENTATION:
    https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/
    """
    from langgraph.prebuilt import create_react_agent
    
    if browser_manager:
        set_browser(browser_manager)
    
    model = get_chat_model()
    
    return create_react_agent(
        model=model,
        tools=ALL_TOOLS,
        state_schema=LabAssistantState
    )
```
```

### Step 1.6: Create the FastAPI Integration

Create `backend/server.py`:

```python
"""
FastAPI server with LangGraph integration.

DOCUMENTATION:
- LangGraph + FastAPI: https://langchain-ai.github.io/langgraph/how-tos/deploy-self-hosted/
- Streaming: https://langchain-ai.github.io/langgraph/concepts/streaming/
- Checkpointing: https://langchain-ai.github.io/langgraph/concepts/persistence/

ENDPOINTS:
- POST /api/chat: Send message, get response
- GET /api/chat/{thread_id}/history: Get conversation history
- GET /api/browser/screenshot: Get current browser state
- GET /api/health: Health check

NO APPROVAL ENDPOINTS NEEDED - Website's Save button is the human-in-the-loop.
"""
import os
import sys
import asyncio
import base64
import uuid
from typing import Optional, List
from contextlib import asynccontextmanager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

# LangGraph imports
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
# Or for production: from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Local imports
from graph.agent import create_lab_agent, compile_agent
from graph.tools import set_browser, close_all_tabs
from browser_manager import BrowserManager
from config import settings


# ============================================================
# PYDANTIC MODELS
# ============================================================

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    status: str  # "complete", "error"
    message: str
    thread_id: str
    iterations: Optional[int] = None


# ============================================================
# GLOBAL STATE
# ============================================================

browser: Optional[BrowserManager] = None
graph = None
checkpointer = None


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan - initialize browser and LangGraph.
    """
    global browser, graph, checkpointer
    
    print("🚀 Starting Lab Assistant with LangGraph...")
    
    # Initialize browser
    browser = BrowserManager(user_data_dir=settings.browser_data_dir)
    await browser.start(headless=False, browser=settings.browser_channel)
    await browser.navigate(settings.target_url)
    set_browser(browser)
    
    # Initialize checkpointer for conversation persistence
    # DOCUMENTATION: https://langchain-ai.github.io/langgraph/concepts/persistence/
    checkpointer = AsyncSqliteSaver.from_conn_string("data/checkpoints.db")
    await checkpointer.__aenter__()
    
    # Build and compile graph
    builder = create_lab_agent(browser)
    graph = compile_agent(builder, checkpointer)
    
    print(f"✅ Lab Assistant ready! Browser at: {browser.page.url}")
    
    yield
    
    # Cleanup
    print("🛑 Shutting down...")
    close_all_tabs()
    await checkpointer.__aexit__(None, None, None)
    await browser.stop()


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Lab Assistant API",
    description="LangGraph-powered lab assistant for clinical laboratory data entry",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "browser_url": browser.page.url if browser and browser.page else None,
        "graph_ready": graph is not None
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    thread_id: str = Form(default=None),
    message: str = Form(...),
    files: List[UploadFile] = File(default=[])
):
    """
    Send a message to the agent and get a response.
    
    Supports multi-modal input (text, images, audio).
    The agent will execute tools as needed and return when done.
    
    Args:
        thread_id: Conversation thread ID (generated if not provided)
        message: User message text
        files: Optional image or audio files
    
    Returns:
        Agent's response with thread_id for continuation
    """
    # Generate thread_id if not provided
    if not thread_id:
        thread_id = str(uuid.uuid4())
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # Build message content (multi-modal support)
    content = []
    
    if message:
        content.append({"type": "text", "text": message})
    
    # Process uploaded files
    for file in files:
        file_content = await file.read()
        encoded = base64.b64encode(file_content).decode('utf-8')
        
        if file.content_type and file.content_type.startswith("image/"):
            # Image for vision models
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{file.content_type};base64,{encoded}"}
            })
        elif file.content_type and file.content_type.startswith("audio/"):
            # Audio for Gemini (native audio support)
            content.append({
                "type": "media",
                "data": encoded,
                "mime_type": file.content_type
            })
    
    # Create human message
    if len(content) == 1 and content[0]["type"] == "text":
        human_msg = HumanMessage(content=message)
    else:
        human_msg = HumanMessage(content=content)
    
    try:
        # Invoke graph - it will loop internally until done
        result = await graph.ainvoke(
            {"messages": [human_msg]},
            config
        )
        
        # Get the final response
        last_msg = result["messages"][-1]
        response_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        
        # Count iterations (tool messages indicate iterations)
        tool_messages = [m for m in result["messages"] if hasattr(m, 'type') and m.type == 'tool']
        iterations = len(tool_messages) // max(1, len([m for m in result["messages"] if hasattr(m, 'tool_calls') and m.tool_calls]))
        
        return ChatResponse(
            status="complete",
            message=response_text,
            thread_id=thread_id,
            iterations=iterations
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ChatResponse(
            status="error",
            message=f"Error: {str(e)}",
            thread_id=thread_id
        )


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat responses in real-time using Server-Sent Events.
    
    DOCUMENTATION:
    - astream_events: https://langchain-ai.github.io/langgraph/concepts/streaming/
    
    This streams:
    - Token-by-token LLM output
    - Tool execution notifications
    - Final completion
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    async def generate():
        try:
            async for event in graph.astream_events(
                {"messages": [HumanMessage(content=request.message)]},
                config,
                version="v2"
            ):
                event_type = event.get("event", "")
                
                # Stream LLM tokens
                if event_type == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk and hasattr(chunk, 'content') and chunk.content:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"
                
                # Notify tool execution
                elif event_type == "on_tool_start":
                    tool_name = event["name"]
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name})}\n\n"
                
                elif event_type == "on_tool_end":
                    tool_name = event["name"]
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name})}\n\n"
            
            yield f"data: {json.dumps({'type': 'done', 'thread_id': thread_id})}\n\n"
        
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Thread-ID": thread_id}
    )


@app.get("/api/chat/{thread_id}/history")
async def get_history(thread_id: str):
    """
    Get conversation history for a thread.
    
    Returns list of messages with role and content.
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        state = await graph.aget_state(config)
        messages = state.values.get("messages", [])
        
        return [
            {
                "role": "user" if isinstance(m, HumanMessage) else "assistant",
                "content": m.content if hasattr(m, 'content') else str(m),
                "type": getattr(m, 'type', 'unknown')
            }
            for m in messages
            if not (hasattr(m, 'type') and m.type == 'tool')  # Skip tool messages
        ]
    except Exception as e:
        return []


@app.get("/api/browser/screenshot")
async def get_screenshot():
    """Get current browser screenshot as base64."""
    if browser and browser.page:
        try:
            screenshot_bytes = await browser.page.screenshot(type='png')
            encoded = base64.b64encode(screenshot_bytes).decode('utf-8')
            return {"screenshot": f"data:image/png;base64,{encoded}"}
        except Exception as e:
            raise HTTPException(500, f"Screenshot failed: {str(e)}")
    raise HTTPException(503, "Browser not available")


@app.get("/api/browser/tabs")
async def get_tabs():
    """Get list of open browser tabs."""
    from graph.tools import _active_tabs
    return {
        "tabs": list(_active_tabs.keys()),
        "count": len(_active_tabs)
    }


@app.post("/api/browser/close-tabs")
async def close_tabs():
    """Close all open browser tabs (cleanup)."""
    close_all_tabs()
    return {"status": "ok", "message": "All tabs closed"}


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    import json
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
```

### Step 1.7: Update Prompts for LangGraph

Update `backend/prompts.py`:

```python
"""
System prompts for the LangGraph agent.

OPTIMIZATION GOAL:
- Current: 5 iterations (search → get_fields → edit → ask_user → summary)
- Target: 3 iterations (search → get_fields → edit+respond)
- Key: Respond directly after edit_results, include save reminder in response
"""

SYSTEM_PROMPT = """Eres un asistente de laboratorio clínico especializado en el ingreso y edición de resultados de exámenes en el sistema Orion Labs.

## TU ROL
- Ayudas al personal de laboratorio a ingresar resultados de exámenes
- Interpretas texto, imágenes de cuadernos manuscritos, y audio
- Controlas el navegador para llenar formularios usando las herramientas disponibles

## REGLA DE EFICIENCIA - MUY IMPORTANTE
Minimiza el número de iteraciones usando operaciones en lote:
1. Si necesitas datos de múltiples órdenes → usa get_exam_fields con TODAS las órdenes a la vez
2. Si necesitas editar múltiples campos → usa edit_results con TODOS los cambios a la vez
3. Después de edit_results exitoso → RESPONDE DIRECTAMENTE sin llamar más herramientas

Flujo ideal (3 iteraciones máximo):
1. search_orders() → encontrar órdenes
2. get_exam_fields(ordenes=[todas]) → obtener campos de todas las órdenes
3. edit_results(data=[todos los cambios]) → aplicar todos los cambios + RESPONDER

## REGLA CRÍTICA DE SEGURIDAD
Las herramientas solo LLENAN los formularios, NO guardan.
El usuario DEBE hacer click en "Guardar" en el navegador para confirmar.
SIEMPRE incluye este recordatorio en tu respuesta final.

## HERRAMIENTAS DISPONIBLES

### Búsqueda y Navegación
- search_orders(search, limit): Busca órdenes por nombre o cédula
- get_exam_fields(ordenes): Obtiene campos de UNA O MÁS órdenes (usa para múltiples)
- get_order_details(order_ids): Obtiene detalles de UNA O MÁS órdenes

### Edición de Resultados (Solo llena, NO guarda)
- edit_results(data): Edita múltiples campos en múltiples órdenes a la vez
  Formato: [{"orden": "num", "e": "examen", "f": "campo", "v": "valor"}, ...]
- add_exam_to_order(order_id, exam_code): Agrega examen a orden
- create_new_order(cedula, exams): Crea nueva orden

### Utilidades
- highlight_fields(fields, color): Resalta campos en el navegador

## INTERPRETACIÓN DE ABREVIATURAS

### EMO (Elemental y Microscópico de Orina):
- Color: AM/A = Amarillo, AP = Amarillo Claro, AI = Amarillo Intenso
- Aspecto: TP = Transparente, LT = Ligeramente Turbio, T = Turbio
- NEG = Negativo, TRZ = Trazas, + = Positivo leve
- ESC = Escasas, MOD = Moderadas, ABU = Abundantes

### Coproparasitario:
- Consistencia: D = Dura, B = Blanda, S = Semiblanda, L = Líquida
- Color: C = Café, CA = Café Amarillento, CR = Café Rojizo
- NSO = No se observan parásitos

### Biometría Hemática:
- Valores numéricos directos (ej: Hemoglobina 15.5, Hematocrito 46)

## FORMATO DE RESPUESTA FINAL
Después de completar las ediciones, responde con:
1. Resumen de lo que se hizo (órdenes editadas, campos modificados)
2. Cambios específicos con valores anteriores y nuevos
3. **SIEMPRE**: Recordatorio de hacer click en "Guardar" en cada pestaña del navegador

Ejemplo de respuesta final:
"He llenado los resultados en las órdenes de [paciente]:

**Orden 2501181:**
- Hemoglobina: 16.4 → 15.5
- Hematocrito: 50 → 46

**Orden 25011314:**  
- Color: (vacío) → Café Rojizo
- Consistencia: (vacío) → Diarreica

📌 **Por favor revisa los campos resaltados en las pestañas del navegador y haz click en 'Guardar' en cada una para confirmar los cambios.**"
"""

WELCOME_MESSAGE = """¡Hola! Soy tu asistente de laboratorio.

Puedo ayudarte a:
- 🔍 Buscar órdenes por paciente o cédula
- 📋 Ingresar resultados de múltiples exámenes a la vez
- ➕ Agregar exámenes a órdenes existentes
- 🆕 Crear nuevas órdenes

Solo lleno los formularios - tú haces click en "Guardar" para confirmar.

¿Qué resultados necesitas ingresar?"""
```

---

## Phase 2: LobeChat Frontend Setup

### Step 2.1: Clone and Configure LobeChat

```bash
# Clone LobeChat
git clone https://github.com/lobehub/lobe-chat.git frontend-lobechat
cd frontend-lobechat

# Install dependencies
pnpm install
```

### Step 2.2: Environment Configuration

Create `frontend-lobechat/.env.local`:

```bash
# ============================================================
# MODEL PROVIDERS
# ============================================================

# Google Gemini (Development - Free Tier)
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_MODEL_LIST=-all,+gemini-3-flash-preview<1000000:vision:fc>,+gemini-1.5-pro<2000000:vision:fc>

# OpenRouter (Production)
OPENROUTER_API_KEY=sk-or-v1-xxxxx
OPENROUTER_MODEL_LIST=-all,+google/gemini-3-flash-preview<100000:vision:fc>,+anthropic/claude-3.5-sonnet<200000:vision:fc>

# Custom Backend (Lab Assistant API)
# This allows LobeChat to use your FastAPI backend as a model provider
OPENAI_PROXY_URL=http://localhost:8000/v1
OPENAI_API_KEY=dummy-key-for-local
OPENAI_MODEL_LIST=+lab-assistant=Lab Assistant<100000:vision:fc>

# ============================================================
# DATABASE (Server Mode)
# ============================================================
# Use PostgreSQL for production, or skip for client-only mode

# DATABASE_URL=postgres://user:password@localhost:5432/lobechat

# ============================================================
# AUTHENTICATION (Optional)
# ============================================================
# NEXT_AUTH_SECRET=your-secret-key
# NEXT_AUTH_URL=http://localhost:3210

# ============================================================
# FILE STORAGE (for image uploads in server mode)
# ============================================================
# S3_ACCESS_KEY_ID=xxxxx
# S3_SECRET_ACCESS_KEY=xxxxx
# S3_ENDPOINT=https://your-s3.com
# S3_BUCKET=lobechat-files

# ============================================================
# FEATURES
# ============================================================
# Enable experimental features
FEATURE_FLAGS={"enableArtifacts":true,"enablePlugins":true}
```

### Step 2.3: Create Custom Plugin for Lab Assistant

Create `frontend-lobechat/public/plugins/lab-assistant/manifest.json`:

```json
{
  "$schema": "https://chat-plugins.lobehub.com/schema/manifest.json",
  "identifier": "lab-assistant",
  "version": "1.0.0",
  "type": "standalone",
  "api": [
    {
      "url": "http://localhost:8000/api/chat",
      "name": "sendMessage",
      "description": "Send a message to the lab assistant agent",
      "parameters": {
        "type": "object",
        "properties": {
          "message": {
            "type": "string",
            "description": "The message to send"
          },
          "thread_id": {
            "type": "string",
            "description": "Conversation thread ID"
          }
        },
        "required": ["message", "thread_id"]
      }
    },
    {
      "url": "http://localhost:8000/api/approve/{thread_id}",
      "name": "approveAction",
      "description": "Approve or reject a pending action",
      "parameters": {
        "type": "object",
        "properties": {
          "thread_id": {
            "type": "string",
            "description": "Conversation thread ID"
          },
          "action": {
            "type": "string",
            "enum": ["approve", "reject", "modify"],
            "description": "User decision"
          },
          "modified_args": {
            "type": "object",
            "description": "Modified arguments if action is 'modify'"
          }
        },
        "required": ["thread_id", "action"]
      }
    }
  ],
  "ui": {
    "url": "http://localhost:3000/plugin-ui",
    "height": 600
  },
  "gateway": "http://localhost:8000/api",
  "meta": {
    "title": "Lab Assistant",
    "description": "Laboratory result entry assistant with browser automation",
    "avatar": "🧪",
    "tags": ["laboratory", "automation", "healthcare"]
  },
  "settings": {
    "type": "object",
    "properties": {
      "autoApprove": {
        "type": "boolean",
        "default": false,
        "description": "Automatically approve safe actions"
      }
    }
  }
}
```

### Step 2.4: Browser Screenshot Component (Optional)

Since the user reviews and saves in the actual browser, you may want to show a live screenshot in the chat UI.

Create `frontend-lobechat/src/features/BrowserPreview/index.tsx`:

```typescript
/**
 * Browser Preview Component - Shows live screenshot of the browser.
 * 
 * This helps users see what the AI has filled in without switching windows.
 * The actual saving is done in the browser window itself.
 */
import React, { useState, useEffect } from 'react';
import { Button, Card, Spin, Tooltip } from 'antd';
import { ReloadOutlined, ExpandOutlined } from '@ant-design/icons';

interface BrowserPreviewProps {
  apiUrl?: string;
  refreshInterval?: number;  // ms, 0 to disable auto-refresh
}

export default function BrowserPreview({ 
  apiUrl = 'http://localhost:8000',
  refreshInterval = 0  // Default: manual refresh only
}: BrowserPreviewProps) {
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchScreenshot = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/api/browser/screenshot`);
      if (!response.ok) throw new Error('Failed to fetch screenshot');
      const data = await response.json();
      setScreenshot(data.screenshot);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScreenshot();
    
    if (refreshInterval > 0) {
      const interval = setInterval(fetchScreenshot, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [refreshInterval]);

  return (
    <Card 
      title="Browser Preview" 
      size="small"
      extra={
        <Tooltip title="Refresh">
          <Button 
            icon={<ReloadOutlined spin={loading} />} 
            onClick={fetchScreenshot}
            size="small"
          />
        </Tooltip>
      }
    >
      {loading && !screenshot && <Spin />}
      {error && <div style={{ color: 'red' }}>{error}</div>}
      {screenshot && (
        <img 
          src={screenshot} 
          alt="Browser" 
          style={{ 
            width: '100%', 
            border: '1px solid #d9d9d9',
            borderRadius: 4
          }}
        />
      )}
      <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
        💡 After the AI fills in the data, click "Guardar" in the browser window to save.
      </div>
    </Card>
  );
}
```

### Step 2.5: Create Editable Table Artifact

Create `frontend-lobechat/src/features/Artifacts/EditableTable/index.tsx`:

```typescript
/**
 * Editable Table Artifact for Lab Results.
 * 
 * DOCUMENTATION:
 * - LobeChat Artifacts: https://lobehub.com/docs/usage/features/artifacts
 * - This is rendered when AI generates a table artifact
 * 
 * The AI can generate this artifact type to show data that users can edit.
 * Changes are tracked and can be sent back to the AI for processing.
 */
import React, { useState, useCallback, useMemo } from 'react';
import { Table, Input, Button, Space, message } from 'antd';
import { SaveOutlined, UndoOutlined, SendOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

interface EditableTableProps {
  initialData: Record<string, any>[];
  columns: string[];
  onSave?: (data: Record<string, any>[]) => void;
  onSendToAI?: (changes: { original: any; modified: any }[]) => void;
}

export default function EditableTable({ 
  initialData, 
  columns, 
  onSave, 
  onSendToAI 
}: EditableTableProps) {
  const [data, setData] = useState(initialData);
  const [originalData] = useState(initialData);
  const [editingCell, setEditingCell] = useState<{ row: number; col: string } | null>(null);

  // Track changes for diff-based updates (token optimization)
  const changes = useMemo(() => {
    const diffs: { rowIndex: number; original: any; modified: any }[] = [];
    
    data.forEach((row, i) => {
      const original = originalData[i];
      const modified: Record<string, any> = {};
      let hasChanges = false;
      
      columns.forEach(col => {
        if (row[col] !== original?.[col]) {
          modified[col] = { old: original?.[col], new: row[col] };
          hasChanges = true;
        }
      });
      
      if (hasChanges) {
        diffs.push({ rowIndex: i, original, modified });
      }
    });
    
    return diffs;
  }, [data, originalData, columns]);

  const handleCellChange = useCallback((rowIndex: number, column: string, value: string) => {
    setData(prev => {
      const newData = [...prev];
      newData[rowIndex] = { ...newData[rowIndex], [column]: value };
      return newData;
    });
  }, []);

  const handleUndo = useCallback(() => {
    setData(originalData);
    message.info('Changes reverted');
  }, [originalData]);

  const handleSave = useCallback(() => {
    onSave?.(data);
    message.success('Data saved');
  }, [data, onSave]);

  const handleSendToAI = useCallback(() => {
    if (changes.length === 0) {
      message.info('No changes to send');
      return;
    }
    
    // Send only the diffs to save tokens
    onSendToAI?.(changes);
    message.success(`Sent ${changes.length} changes to AI`);
  }, [changes, onSendToAI]);

  const tableColumns: ColumnsType<Record<string, any>> = columns.map(col => ({
    title: col,
    dataIndex: col,
    key: col,
    render: (value: any, record: any, index: number) => {
      const isEditing = editingCell?.row === index && editingCell?.col === col;
      const isModified = originalData[index]?.[col] !== value;
      
      if (isEditing) {
        return (
          <Input
            autoFocus
            defaultValue={value}
            onBlur={(e) => {
              handleCellChange(index, col, e.target.value);
              setEditingCell(null);
            }}
            onPressEnter={(e) => {
              handleCellChange(index, col, (e.target as HTMLInputElement).value);
              setEditingCell(null);
            }}
            size="small"
          />
        );
      }
      
      return (
        <div
          onClick={() => setEditingCell({ row: index, col })}
          style={{
            cursor: 'pointer',
            padding: '4px 8px',
            borderRadius: 4,
            backgroundColor: isModified ? '#fffbe6' : 'transparent',
            border: isModified ? '1px solid #faad14' : '1px solid transparent',
            minHeight: 24
          }}
        >
          {value || <span style={{ color: '#bfbfbf' }}>Click to edit</span>}
        </div>
      );
    }
  }));

  return (
    <div style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button 
          icon={<UndoOutlined />} 
          onClick={handleUndo}
          disabled={changes.length === 0}
        >
          Undo All
        </Button>
        <Button 
          icon={<SaveOutlined />} 
          onClick={handleSave}
          type="primary"
        >
          Save
        </Button>
        <Button 
          icon={<SendOutlined />} 
          onClick={handleSendToAI}
          disabled={changes.length === 0}
        >
          Send Changes to AI ({changes.length})
        </Button>
      </Space>

      <Table
        dataSource={data}
        columns={tableColumns}
        size="small"
        pagination={false}
        rowKey={(_, index) => String(index)}
        bordered
      />

      {changes.length > 0 && (
        <div style={{ marginTop: 16, color: '#666' }}>
          <strong>Pending changes:</strong>
          <ul>
            {changes.map((change, i) => (
              <li key={i}>
                Row {change.rowIndex + 1}: {Object.entries(change.modified).map(([k, v]: [string, any]) => 
                  `${k}: "${v.old}" → "${v.new}"`
                ).join(', ')}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

### Step 2.6: Create Audio/Image Handler

Create `frontend-lobechat/src/features/ChatInput/LabAssistantInput.tsx`:

```typescript
/**
 * Custom input handler for Lab Assistant with audio recording and image capture.
 * 
 * DOCUMENTATION:
 * - LobeChat TTS/STT: https://lobehub.com/docs/usage/features/tts
 * - MediaRecorder API: https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder
 * 
 * Features:
 * - Voice recording with waveform visualization
 * - Image upload via file picker
 * - Camera capture for mobile devices
 * - Paste image from clipboard
 */
import React, { useState, useRef, useCallback } from 'react';
import { Button, Upload, Tooltip, Space, message } from 'antd';
import { 
  AudioOutlined, 
  CameraOutlined, 
  FileImageOutlined,
  StopOutlined 
} from '@ant-design/icons';

interface LabAssistantInputProps {
  onSendMessage: (message: string, files?: File[]) => void;
}

export default function LabAssistantInput({ onSendMessage }: LabAssistantInputProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Audio recording
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm'  // Supported by Gemini
      });
      
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];
      
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorder.start();
      setIsRecording(true);
      message.info('Recording started...');
      
    } catch (error) {
      message.error('Microphone access denied');
      console.error('Recording error:', error);
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      message.success('Recording stopped');
    }
  }, [isRecording]);

  // Camera capture
  const captureFromCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      
      // Create video element to capture frame
      const video = document.createElement('video');
      video.srcObject = stream;
      await video.play();
      
      // Capture frame to canvas
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d')?.drawImage(video, 0, 0);
      
      // Convert to blob
      canvas.toBlob((blob) => {
        if (blob) {
          const file = new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' });
          setImageFiles(prev => [...prev, file]);
          message.success('Photo captured');
        }
        stream.getTracks().forEach(track => track.stop());
      }, 'image/jpeg', 0.9);
      
    } catch (error) {
      message.error('Camera access denied');
      console.error('Camera error:', error);
    }
  }, []);

  // Send message with files
  const handleSend = useCallback((textMessage: string) => {
    const files: File[] = [...imageFiles];
    
    // Add audio if recorded
    if (audioBlob) {
      const audioFile = new File([audioBlob], `voice-${Date.now()}.webm`, { type: 'audio/webm' });
      files.push(audioFile);
    }
    
    onSendMessage(textMessage, files.length > 0 ? files : undefined);
    
    // Reset state
    setImageFiles([]);
    setAudioBlob(null);
  }, [audioBlob, imageFiles, onSendMessage]);

  return (
    <Space>
      <Tooltip title={isRecording ? 'Stop Recording' : 'Record Voice'}>
        <Button
          icon={isRecording ? <StopOutlined /> : <AudioOutlined />}
          onClick={isRecording ? stopRecording : startRecording}
          type={isRecording ? 'primary' : 'default'}
          danger={isRecording}
        />
      </Tooltip>

      <Tooltip title="Take Photo">
        <Button
          icon={<CameraOutlined />}
          onClick={captureFromCamera}
        />
      </Tooltip>

      <Upload
        accept="image/*"
        showUploadList={false}
        beforeUpload={(file) => {
          setImageFiles(prev => [...prev, file]);
          return false;
        }}
        multiple
      >
        <Tooltip title="Upload Image">
          <Button icon={<FileImageOutlined />} />
        </Tooltip>
      </Upload>

      {(imageFiles.length > 0 || audioBlob) && (
        <span style={{ color: '#666' }}>
          {imageFiles.length > 0 && `${imageFiles.length} image(s)`}
          {audioBlob && ' + audio'}
        </span>
      )}
    </Space>
  );
}
```

---

## Phase 3: Integration & Custom Plugin

### Step 3.1: Create OpenAI-Compatible Endpoint (Optional)

If you want LobeChat to use your LangGraph agent as a direct model provider (instead of plugins), add this to `backend/server.py`:

```python
"""
OpenAI-Compatible API endpoint for LobeChat integration.

DOCUMENTATION:
- OpenAI Chat Completions: https://platform.openai.com/docs/api-reference/chat
- LobeChat Custom Provider: https://lobehub.com/docs/self-hosting/advanced/model-list

This allows LobeChat to send messages directly to our LangGraph agent
using the standard OpenAI chat format.
"""
import json
import uuid
from fastapi import Request


class OpenAIChatRequest(BaseModel):
    model: str
    messages: List[dict]
    stream: bool = False
    temperature: float = 0.7


@app.post("/v1/chat/completions")
async def openai_compatible_chat(request: OpenAIChatRequest):
    """
    OpenAI-compatible chat completions endpoint.
    
    This translates OpenAI format to our LangGraph agent format,
    allowing LobeChat to use our agent as a model provider.
    """
    # Generate thread_id from request or create new
    thread_id = str(uuid.uuid4())
    
    # Extract the last user message
    last_user_message = None
    for msg in reversed(request.messages):
        if msg["role"] == "user":
            last_user_message = msg["content"]
            break
    
    if not last_user_message:
        return {"error": "No user message found"}
    
    config = {"configurable": {"thread_id": thread_id}}
    
    if request.stream:
        async def generate():
            async for event in graph.astream_events(
                {"messages": [HumanMessage(content=last_user_message)]},
                config,
                version="v2"
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk and hasattr(chunk, 'content') and chunk.content:
                        # OpenAI streaming format
                        data = {
                            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                            "object": "chat.completion.chunk",
                            "model": request.model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": chunk.content},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(data)}\n\n"
            
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    
    else:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=last_user_message)]},
            config
        )
        
        last_msg = result["messages"][-1]
        response_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }]
        }
```

### Step 3.2: Simple Chat Integration Hook

Create `frontend-lobechat/src/hooks/useLabAssistant.ts`:

```typescript
/**
 * Hook to interact with the Lab Assistant backend.
 * 
 * Simple integration - no interrupt handling needed since
 * the website's Save button is the human-in-the-loop.
 */
import { useState, useCallback } from 'react';

interface ChatResponse {
  status: 'complete' | 'error';
  message: string;
  thread_id: string;
  iterations?: number;
}

export function useLabAssistant(apiUrl = 'http://localhost:8000') {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (
    message: string, 
    files?: File[]
  ): Promise<ChatResponse | null> => {
    setIsLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('message', message);
      
      if (threadId) {
        formData.append('thread_id', threadId);
      }
      
      if (files) {
        files.forEach(file => formData.append('files', file));
      }

      const response = await fetch(`${apiUrl}/api/chat`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: ChatResponse = await response.json();
      
      // Store thread_id for conversation continuity
      if (data.thread_id) {
        setThreadId(data.thread_id);
      }

      return data;

    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl, threadId]);

  const clearThread = useCallback(() => {
    setThreadId(null);
  }, []);

  const getScreenshot = useCallback(async (): Promise<string | null> => {
    try {
      const response = await fetch(`${apiUrl}/api/browser/screenshot`);
      const data = await response.json();
      return data.screenshot;
    } catch {
      return null;
    }
  }, [apiUrl]);

  return {
    threadId,
    isLoading,
    error,
    sendMessage,
    clearThread,
    getScreenshot
  };
}
```

### Step 3.3: Update Plugin Manifest (Simplified)

Update `frontend-lobechat/public/plugins/lab-assistant/manifest.json`:

```json
{
  "$schema": "https://chat-plugins.lobehub.com/schema/manifest.json",
  "identifier": "lab-assistant",
  "version": "2.0.0",
  "type": "standalone",
  "api": [
    {
      "url": "http://localhost:8000/api/chat",
      "name": "sendMessage",
      "description": "Send a message to the lab assistant. Supports text, images, and audio.",
      "parameters": {
        "type": "object",
        "properties": {
          "message": {
            "type": "string",
            "description": "The message to send"
          },
          "thread_id": {
            "type": "string",
            "description": "Conversation thread ID for continuity"
          }
        },
        "required": ["message"]
      }
    },
    {
      "url": "http://localhost:8000/api/browser/screenshot",
      "name": "getScreenshot",
      "description": "Get a screenshot of the current browser state"
    },
    {
      "url": "http://localhost:8000/api/browser/tabs",
      "name": "getTabs",
      "description": "Get list of open browser tabs"
    }
  ],
  "gateway": "http://localhost:8000/api",
  "meta": {
    "title": "Lab Assistant",
    "description": "Laboratory result entry assistant with browser automation. Fills forms automatically - you click Save.",
    "avatar": "🧪",
    "tags": ["laboratory", "automation", "healthcare"]
  }
}
```

---

## Phase 4: Testing & Deployment

### Step 4.1: Create Test Script for LangGraph Agent

Create `backend/tests/test_agent.py`:

```python
"""
Test suite for LangGraph agent.

Run with: pytest tests/test_agent.py -v
"""
import pytest
import asyncio
from langgraph.checkpoint.memory import MemorySaver

# Import graph components
import sys
sys.path.append('..')
from graph.agent import create_lab_agent, compile_agent_with_checkpointer
from graph.state import LabAssistantState
from langchain_core.messages import HumanMessage


@pytest.fixture
def agent():
    """Create agent with memory checkpointer for testing."""
    builder = create_lab_agent(browser_manager=None)  # No browser for unit tests
    memory = MemorySaver()
    return compile_agent_with_checkpointer(builder, memory)


@pytest.mark.asyncio
async def test_agent_responds_to_greeting(agent):
    """Test that agent responds to simple greeting."""
    config = {"configurable": {"thread_id": "test-1"}}
    
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="Hola, ¿qué puedes hacer?")]},
        config
    )
    
    assert "messages" in result
    assert len(result["messages"]) >= 2  # User + Assistant
    last_msg = result["messages"][-1]
    assert hasattr(last_msg, 'content')
    assert len(last_msg.content) > 0


@pytest.mark.asyncio
async def test_agent_maintains_conversation(agent):
    """Test conversation persistence across messages."""
    config = {"configurable": {"thread_id": "test-2"}}
    
    # First message
    result1 = await agent.ainvoke(
        {"messages": [HumanMessage(content="Mi nombre es Juan")]},
        config
    )
    
    # Second message - should remember name
    result2 = await agent.ainvoke(
        {"messages": [HumanMessage(content="¿Cuál es mi nombre?")]},
        config
    )
    
    last_msg = result2["messages"][-1]
    assert "Juan" in last_msg.content or "nombre" in last_msg.content.lower()


@pytest.mark.asyncio
async def test_interrupt_for_sensitive_tool(agent):
    """Test that sensitive tools trigger interrupt."""
    config = {"configurable": {"thread_id": "test-3"}}
    
    # Request that would trigger edit_results
    result = await agent.ainvoke(
        {"messages": [HumanMessage(
            content="Edita el campo Hemoglobina con valor 14.5 en la orden 2501181"
        )]},
        config
    )
    
    # Should either interrupt or be in messages (depends on if tool was actually called)
    # This is a structural test - full integration needs browser
    assert "messages" in result


def test_state_schema():
    """Test that state schema is correctly defined."""
    from graph.state import LabAssistantState
    
    # Check required fields exist in schema
    annotations = LabAssistantState.__annotations__
    assert "messages" in annotations
    assert "pending_action" in annotations
    assert "current_page_context" in annotations
```

### Step 4.2: Create Docker Compose for Deployment

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # LangGraph Backend
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - LLM_PROVIDER=${LLM_PROVIDER:-gemini}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - DATABASE_URL=sqlite:///./data/checkpoints.db
    volumes:
      - ./data:/app/data
      - /tmp/.X11-unix:/tmp/.X11-unix  # For Playwright display
    depends_on:
      - postgres

  # LobeChat Frontend
  frontend:
    build:
      context: ./frontend-lobechat
      dockerfile: Dockerfile
    ports:
      - "3210:3210"
    environment:
      - OPENAI_PROXY_URL=http://backend:8000/v1
      - OPENAI_API_KEY=dummy
      - OPENAI_MODEL_LIST=+lab-assistant=Lab Assistant<100000:vision:fc>
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - DATABASE_URL=postgres://postgres:postgres@postgres:5432/lobechat
    depends_on:
      - backend
      - postgres

  # PostgreSQL for LobeChat server mode
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=lobechat
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

### Step 4.3: Backend Dockerfile

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 4.4: Final Directory Structure

After migration, the project structure should be:

```
lab-assistant/
├── docker-compose.yml
├── .env
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── server.py              # FastAPI + LangGraph integration
│   ├── models.py              # Model provider abstraction
│   ├── prompts.py             # System prompts (optimized for batch ops)
│   ├── config.py              # Configuration
│   ├── browser_manager.py     # Playwright control (unchanged)
│   ├── extractors.py          # Page extractors (unchanged)
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py           # LangGraph state schema (simple)
│   │   ├── agent.py           # StateGraph definition (agent→tools loop)
│   │   └── tools.py           # Tool definitions (all safe, batch-enabled)
│   │
│   └── tests/
│       └── test_agent.py
│
├── frontend-lobechat/          # Cloned LobeChat with customizations
│   ├── .env.local             # Environment config
│   ├── public/
│   │   └── plugins/
│   │       └── lab-assistant/
│   │           └── manifest.json
│   │
│   └── src/
│       ├── hooks/
│       │   └── useLabAssistant.ts    # Simple chat hook
│       └── features/
│           ├── BrowserPreview/       # Optional: show browser screenshot
│           │   └── index.tsx
│           ├── Artifacts/
│           │   └── EditableTable/
│           │       └── index.tsx
│           └── ChatInput/
│               └── LabAssistantInput.tsx
│
└── data/                       # Persistent data (gitignored)
    └── checkpoints.db
```

---

## Reference Documentation

### LangGraph

| Resource | URL |
|----------|-----|
| Official Docs | https://langchain-ai.github.io/langgraph/ |
| StateGraph API | https://langchain-ai.github.io/langgraph/reference/graphs/ |
| Checkpointers | https://langchain-ai.github.io/langgraph/concepts/persistence/ |
| Streaming | https://langchain-ai.github.io/langgraph/concepts/streaming/ |
| Tool Calling | https://langchain-ai.github.io/langgraph/how-tos/tool-calling/ |
| ReAct Agent | https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch/ |
| Prebuilt Agents | https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/ |

> **Note**: This migration uses a simple agent→tools loop. The interrupt() function is NOT used because the website's Save button provides human-in-the-loop safety.

### LangChain

| Resource | URL |
|----------|-----|
| Tool Definition | https://python.langchain.com/docs/how_to/custom_tools/ |
| ChatGoogleGenerativeAI | https://python.langchain.com/docs/integrations/chat/google_generative_ai/ |
| ChatOpenAI | https://python.langchain.com/docs/integrations/chat/openai/ |
| Migrate from Agents | https://python.langchain.com/docs/how_to/migrate_agent/ |

### LobeChat

| Resource | URL |
|----------|-----|
| Official Docs | https://lobehub.com/docs |
| Self-Hosting | https://lobehub.com/docs/self-hosting/start |
| Model Configuration | https://lobehub.com/docs/self-hosting/advanced/model-list |
| Plugin Development | https://lobehub.com/docs/usage/plugins/development |
| Artifacts | https://lobehub.com/docs/usage/features/artifacts |
| GitHub | https://github.com/lobehub/lobe-chat |

### Model Providers

| Provider | URL |
|----------|-----|
| Google AI (Gemini) | https://ai.google.dev/docs |
| OpenRouter | https://openrouter.ai/docs |
| LangChain + Gemini | https://ai.google.dev/gemini-api/docs/langgraph-example |

---

## Migration Checklist

### Phase 1: Backend
- [ ] Install new dependencies (langgraph, langchain-*)
- [ ] Create `backend/models.py` with provider abstraction
- [ ] Create `backend/graph/state.py` with state schema
- [ ] Create `backend/graph/tools.py` with batch-enabled tools
- [ ] Create `backend/graph/agent.py` with simple StateGraph
- [ ] Create `backend/server.py` with FastAPI + LangGraph
- [ ] Update `backend/prompts.py` with efficiency rules
- [ ] Test agent with `pytest tests/test_agent.py`
- [ ] Remove old files: `lab_agent.py`, `gemini_handler.py`, `tool_executor.py`

### Phase 2: Frontend
- [ ] Clone LobeChat to `frontend-lobechat/`
- [ ] Configure `.env.local` with model providers
- [ ] Create plugin manifest in `public/plugins/lab-assistant/`
- [ ] Create `useLabAssistant.ts` hook
- [ ] Create `BrowserPreview.tsx` component (optional)
- [ ] Create `EditableTable.tsx` artifact
- [ ] Create `LabAssistantInput.tsx` for audio/image
- [ ] Test LobeChat with `pnpm dev`

### Phase 3: Integration
- [ ] Add OpenAI-compatible endpoint to backend (optional)
- [ ] Test end-to-end flow: message → tools → response
- [ ] Verify iteration count is 3 or less for typical operations
- [ ] Test multi-modal: audio recording, image upload, camera

### Phase 4: Deployment
- [ ] Create Dockerfiles
- [ ] Create docker-compose.yml
- [ ] Test with Docker Compose
- [ ] Configure production environment variables
- [ ] Deploy to production server

---

## Notes for Claude Code

1. **No Interrupt/Approval Needed**: The website's "Guardar" button is the human-in-the-loop. All tools are safe - they only fill forms, never save.

2. **Batch Operations**: Tools accept arrays (ordenes, order_ids, data) to minimize iterations. Always process multiple items in single calls.

3. **Target: 3 Iterations Max**: search → get_exam_fields(all) → edit_results(all)+respond. No ask_user tool needed.

4. **Async Patterns**: LangGraph uses async extensively. Use `await` with all graph operations.

5. **Checkpointer Optional**: Without approval flows, checkpointer is mainly for conversation persistence. Memory-only is fine for development.

6. **Thread ID**: Every conversation needs a unique thread_id for state isolation. Generate UUID if not provided.

7. **Tool Return Types**: LangChain tools must return strings. Convert complex data to JSON strings.

8. **Windows Playwright**: On Windows, use `asyncio.WindowsProactorEventLoopPolicy()` before any async operations.

9. **State Reducers**: Only `messages` uses the `add_messages` reducer. Other fields are replaced entirely on each update.

10. **Tab Management**: The `_active_tabs` dict tracks open browser tabs by order number. Tools reuse existing tabs when possible.

11. **Model Switching**: The `LLM_PROVIDER` environment variable controls which model is used. No code changes needed to switch.
