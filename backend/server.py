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
import json
import logging
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Set up Windows event loop policy if on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

# LangGraph imports
from langgraph.checkpoint.memory import MemorySaver
# For production with SQLite:
# from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Local imports
from graph.agent import create_lab_agent, compile_agent
from graph.tools import set_browser, close_all_tabs, get_active_tabs
from browser_manager import BrowserManager
from extractors import EXTRACT_ORDENES_JS
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
initial_orders_context: str = ""  # Store initial orders for context
orders_context_sent: bool = False  # Track if we've sent valid orders context


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def is_logged_in() -> bool:
    """Check if the browser is logged in (not on login page)."""
    if browser and browser.page:
        return "/login" not in browser.page.url
    return False


async def get_orders_context() -> str:
    """
    Get orders context, checking login state first.
    Returns empty string with login message if not logged in.
    Returns orders table if logged in and orders found.
    """
    global browser, initial_orders_context, orders_context_sent

    if not is_logged_in():
        logger.info("[Context] User not logged in - browser is on login page")
        return "⚠️ SESIÓN NO INICIADA: El navegador está en la página de login. Por favor, inicia sesión en el navegador para que pueda acceder a las órdenes del laboratorio."

    # If we haven't sent valid orders yet, try to extract them
    if not orders_context_sent or not initial_orders_context:
        logger.info("[Context] Extracting orders context...")
        initial_orders_context = await extract_initial_context()
        if initial_orders_context and "Órdenes Recientes" in initial_orders_context:
            orders_context_sent = True
            logger.info(f"[Context] Extracted {initial_orders_context.count('|') // 8} orders")

    return initial_orders_context


# ============================================================
# LIFESPAN
# ============================================================

async def extract_initial_context() -> str:
    """Extract initial orders list from the page for AI context."""
    global browser
    try:
        # Make sure we're on the orders page
        if "/ordenes" not in browser.page.url:
            logger.info("[Context] Navigating to orders page...")
            await browser.page.goto("https://laboratoriofranz.orion-labs.com/ordenes", timeout=30000)

        await browser.page.wait_for_timeout(2000)  # Wait for page to load
        ordenes = await browser.page.evaluate(EXTRACT_ORDENES_JS)
        if ordenes:
            lines = ["# Órdenes Recientes"]
            lines.append("| # | Orden | Fecha | Paciente | Cédula | Estado | ID |")
            lines.append("|---|-------|-------|----------|--------|--------|-----|")
            for i, o in enumerate(ordenes[:15]):
                paciente = (o.get('paciente', '') or '')[:30]
                lines.append(f"| {i+1} | {o.get('num','')} | {o.get('fecha','')} | {paciente} | {o.get('cedula','')} | {o.get('estado','')} | {o.get('id','')} |")
            lines.append("")
            lines.append("*Usa 'num' para get_exam_fields(), 'id' para get_order_details()*")
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Could not extract initial context: {e}")
    return ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan - initialize browser and LangGraph.
    """
    global browser, graph, checkpointer, initial_orders_context

    print("Starting Lab Assistant with LangGraph...")

    # Create data directory if it doesn't exist
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)

    # Initialize browser
    browser = BrowserManager(user_data_dir=settings.browser_data_dir)
    await browser.start(headless=settings.headless, browser=settings.browser_channel)
    await browser.navigate(settings.target_url)
    set_browser(browser)

    # Extract initial orders context (will handle login state)
    initial_orders_context = await get_orders_context()
    if initial_orders_context and "Órdenes Recientes" in initial_orders_context:
        logger.info(f"Extracted initial context with {initial_orders_context.count('|') // 8} orders")
    elif "SESIÓN NO INICIADA" in initial_orders_context:
        logger.warning("[Startup] Not logged in - waiting for user to login")

    # Initialize checkpointer for conversation persistence
    # Using MemorySaver for development (in-memory, not persistent across restarts)
    # For production, use AsyncSqliteSaver or PostgresSaver
    checkpointer = MemorySaver()

    # Build and compile graph
    builder = create_lab_agent(browser)
    graph = compile_agent(builder, checkpointer)

    print(f"Lab Assistant ready! Browser at: {browser.page.url}")

    yield

    # Cleanup
    print("Shutting down...")
    close_all_tabs()
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

        # Count iterations (based on tool messages)
        tool_messages = [m for m in result["messages"] if hasattr(m, 'type') and getattr(m, 'type', None) == 'tool']
        iterations = len(tool_messages)

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
            if not (hasattr(m, 'type') and getattr(m, 'type', None) == 'tool')  # Skip tool messages
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
    active_tabs = get_active_tabs()
    return {
        "tabs": list(active_tabs.keys()),
        "count": len(active_tabs)
    }


@app.post("/api/browser/close-tabs")
async def close_tabs():
    """Close all open browser tabs (cleanup)."""
    close_all_tabs()
    return {"status": "ok", "message": "All tabs closed"}


# ============================================================
# OPENAI-COMPATIBLE ENDPOINT (Optional - for LobeChat integration)
# ============================================================

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
    import time as time_module

    # Debug: log raw request
    logger.debug(f"[Request] Messages count: {len(request.messages)}")
    for i, msg in enumerate(request.messages):
        content = msg.get('content', '')
        # Handle multimodal content (list with text/images)
        if isinstance(content, list):
            content_summary = []
            for part in content:
                if isinstance(part, dict):
                    if part.get('type') == 'text':
                        content_summary.append(f"text:{part.get('text', '')[:50]}")
                    elif part.get('type') == 'image_url':
                        content_summary.append("[IMAGE]")
                    else:
                        content_summary.append(f"[{part.get('type', 'unknown')}]")
                else:
                    content_summary.append(str(part)[:30])
            content_str = ', '.join(content_summary)
        else:
            content_str = str(content)[:100]
        logger.debug(f"[Request] [{i}] role={msg.get('role')}, content={content_str}")

    # Detect and reject LobeChat's auxiliary requests (topic naming, translation, etc.)
    # These have role=developer/system with summarization/translation prompts
    for msg in request.messages:
        role = msg.get("role", "")
        if role in ["developer", "system"]:
            content = str(msg.get("content", "")).lower()
            if any(keyword in content for keyword in ["summarizer", "summarize", "title", "translate", "translation", "compress"]):
                logger.info(f"[Request] Skipping auxiliary request (topic naming/translation)")
                # Return a simple response without invoking the agent
                response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
                created_time = int(time_module.time())
                if request.stream:
                    async def simple_stream():
                        data = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": request.model,
                            "choices": [{"index": 0, "delta": {"content": "Lab Assistant"}, "finish_reason": None}]
                        }
                        yield f"data: {json.dumps(data)}\n\n"
                        final = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": request.model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                        }
                        yield f"data: {json.dumps(final)}\n\n"
                        yield "data: [DONE]\n\n"
                    return StreamingResponse(simple_stream(), media_type="text/event-stream")
                else:
                    return {
                        "id": response_id,
                        "object": "chat.completion",
                        "created": created_time,
                        "model": request.model,
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Lab Assistant"}, "finish_reason": "stop"}]
                    }

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # Convert OpenAI-format messages to LangGraph messages
    # This preserves full conversation history from the frontend
    conversation_messages = []
    for msg in request.messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Handle multimodal content (images) - convert to LangChain format
        if isinstance(content, list):
            # Convert OpenAI multimodal format to LangChain format
            lc_content = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        lc_content.append({"type": "text", "text": part.get("text", "")})
                    elif part.get("type") == "image_url":
                        image_url = part.get("image_url", {})
                        url = image_url.get("url", "") if isinstance(image_url, dict) else image_url
                        lc_content.append({"type": "image_url", "image_url": {"url": url}})
            content = lc_content if lc_content else ""

        if role == "user":
            conversation_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            conversation_messages.append(AIMessage(content=content))
        # Skip system/developer roles - they're handled separately

    if not conversation_messages:
        logger.error("No messages found in request")
        return {"error": "No messages found"}

    # Get the last user message for logging
    last_user_message = None
    for msg in reversed(request.messages):
        if msg["role"] == "user":
            last_user_message = msg["content"]
            break

    logger.info("=" * 60)
    # Handle multimodal user message for logging
    if isinstance(last_user_message, list):
        msg_parts = []
        for part in last_user_message:
            if isinstance(part, dict):
                if part.get('type') == 'text':
                    msg_parts.append(part.get('text', '')[:100])
                elif part.get('type') == 'image_url':
                    msg_parts.append('[IMAGE]')
                else:
                    msg_parts.append(f"[{part.get('type', 'unknown')}]")
        user_msg_display = ' + '.join(msg_parts)
    else:
        user_msg_display = str(last_user_message)[:200]
    logger.info(f"USER MESSAGE: {user_msg_display}{'...' if len(str(last_user_message)) > 200 else ''}")
    logger.info(f"Thread ID: {thread_id}, Stream: {request.stream}, History: {len(conversation_messages)} messages")

    if request.stream:
        async def generate():
            global orders_context_sent
            full_response = []
            response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"  # Same ID for all chunks
            created_time = int(time_module.time())  # Unix timestamp

            # Step tracking for enumeration
            step_counter = 0
            total_input_tokens = 0
            total_output_tokens = 0

            # Gemini pricing (per 1M tokens) - adjust based on model
            # Gemini 3 Flash Preview: $0.50 input, $3.00 output (incl. thinking tokens)
            INPUT_PRICE_PER_1M = 0.50
            OUTPUT_PRICE_PER_1M = 3.00

            try:
                # Check if this is first message in conversation (from frontend history)
                is_first_message = len(conversation_messages) <= 2  # Just system + first user msg

                # Get current context (checks login state, fetches orders if needed)
                current_context = await get_orders_context()

                # Pass full conversation history to the graph
                initial_state = {"messages": conversation_messages}

                # Include context if: first message OR we haven't sent valid orders yet
                should_include_context = is_first_message or not orders_context_sent
                if should_include_context and current_context:
                    initial_state["current_page_context"] = current_context
                    if "SESIÓN NO INICIADA" in current_context:
                        logger.info("[Chat] Not logged in - sending login reminder")
                    else:
                        logger.info("[Chat] Including orders context")

                async for event in graph.astream_events(
                    initial_state,
                    config,
                    version="v2"
                ):
                    event_type = event.get("event", "")

                    # Track LLM calls for step enumeration
                    if event_type == "on_chat_model_start":
                        step_counter += 1
                        logger.info(f"[Step {step_counter}] LLM call started")

                    # Stream tool calls to show "thinking" in LobeChat
                    if event_type == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_input = event.get("data", {}).get("input", {})
                        logger.info(f"TOOL CALL: {tool_name}")
                        logger.debug(f"  Input: {json.dumps(tool_input, ensure_ascii=False)[:500]}")

                        # Send tool call as a "thinking" step to frontend with step number
                        tool_display = f"**[{step_counter}]** 🔧 **{tool_name}**"
                        if tool_input:
                            # Show key parameters
                            params = []
                            for k, v in tool_input.items():
                                if isinstance(v, str) and len(v) < 50:
                                    params.append(f"{k}={v}")
                                elif isinstance(v, list) and len(v) < 5:
                                    params.append(f"{k}={v}")
                            if params:
                                tool_display += f" ({', '.join(params[:3])})"
                        tool_display += "\n"

                        data = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": request.model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": tool_display},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(data)}\n\n"

                    elif event_type == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        tool_output = event.get("data", {}).get("output", "")
                        logger.info(f"TOOL RESULT: {tool_name}")
                        logger.debug(f"  Output: {str(tool_output)[:500]}")

                        # Send brief result indicator
                        result_display = f"✓ {tool_name} completado\n\n"
                        data = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": request.model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": result_display},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(data)}\n\n"

                    elif event_type == "on_chat_model_stream":
                        chunk = event["data"].get("chunk")
                        if chunk and hasattr(chunk, 'content') and chunk.content:
                            # Handle both string and list content (Gemini 3 with thinking)
                            content = chunk.content
                            if isinstance(content, list):
                                # Extract text parts only, skip thinking parts
                                text_parts = [p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'text']
                                content = ''.join(text_parts)
                            if content:
                                full_response.append(content)
                                data = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_time,
                                    "model": request.model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": content},
                                        "finish_reason": None
                                    }]
                                }
                                yield f"data: {json.dumps(data)}\n\n"

                    # Handle non-streaming model responses (after key rotation) and extract token usage
                    elif event_type == "on_chat_model_end":
                        output = event.get("data", {}).get("output")

                        # Try to extract token usage from response
                        if output:
                            # Check for usage_metadata (Gemini)
                            usage = getattr(output, 'usage_metadata', None)
                            if usage:
                                input_tokens = getattr(usage, 'input_tokens', 0) or getattr(usage, 'prompt_token_count', 0) or 0
                                output_tokens = getattr(usage, 'output_tokens', 0) or getattr(usage, 'candidates_token_count', 0) or 0
                                total_input_tokens += input_tokens
                                total_output_tokens += output_tokens
                                logger.info(f"[Step {step_counter}] Tokens: in={input_tokens}, out={output_tokens}")

                            # Also check response_metadata for langchain
                            resp_meta = getattr(output, 'response_metadata', {})
                            if resp_meta and 'usage_metadata' in resp_meta:
                                usage_meta = resp_meta['usage_metadata']
                                input_tokens = usage_meta.get('prompt_token_count', 0)
                                output_tokens = usage_meta.get('candidates_token_count', 0)
                                if input_tokens or output_tokens:
                                    total_input_tokens += input_tokens
                                    total_output_tokens += output_tokens
                                    logger.info(f"[Step {step_counter}] Tokens (from meta): in={input_tokens}, out={output_tokens}")

                        if output and hasattr(output, 'content') and output.content:
                            content = output.content
                            if isinstance(content, list):
                                text_parts = [p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'text']
                                content = ''.join(text_parts)
                            # Only send if we haven't already streamed this content
                            if content and content not in ''.join(full_response):
                                full_response.append(content)
                                data = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_time,
                                    "model": request.model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": content},
                                        "finish_reason": None
                                    }]
                                }
                                yield f"data: {json.dumps(data)}\n\n"

                if full_response:
                    logger.info(f"AI RESPONSE: {''.join(full_response)[:300]}{'...' if len(''.join(full_response)) > 300 else ''}")

                # Calculate and display usage summary
                total_tokens = total_input_tokens + total_output_tokens
                input_cost = (total_input_tokens / 1_000_000) * INPUT_PRICE_PER_1M
                output_cost = (total_output_tokens / 1_000_000) * OUTPUT_PRICE_PER_1M
                total_cost = input_cost + output_cost

                # Send usage summary at the end
                usage_summary = f"\n\n---\n📊 **Stats**: {step_counter} LLM calls"
                if total_tokens > 0:
                    usage_summary += f" | Tokens: {total_input_tokens:,} in + {total_output_tokens:,} out = {total_tokens:,}"
                    usage_summary += f" | Est. cost: ${total_cost:.6f}"
                usage_summary += "\n"

                data = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": usage_summary},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(data)}\n\n"

                logger.info(f"[Usage] Steps: {step_counter}, Input: {total_input_tokens}, Output: {total_output_tokens}, Cost: ${total_cost:.6f}")

                # Send final chunk with finish_reason to signal completion
                final_chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"Stream error: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

    else:
        try:
            # Check if this is first message in conversation (from frontend history)
            is_first_message = len(conversation_messages) <= 2  # Just system + first user msg

            # Get current context (checks login state, fetches orders if needed)
            current_context = await get_orders_context()

            # Pass full conversation history to the graph
            initial_state = {"messages": conversation_messages}

            # Include context if: first message OR we haven't sent valid orders yet
            should_include_context = is_first_message or not orders_context_sent
            if should_include_context and current_context:
                initial_state["current_page_context"] = current_context
                if "SESIÓN NO INICIADA" in current_context:
                    logger.info("[Chat] Not logged in - sending login reminder")
                else:
                    logger.info("[Chat] Including orders context")

            logger.info("Invoking LangGraph agent...")
            result = await graph.ainvoke(initial_state, config)

            # Log all messages for debugging
            for i, msg in enumerate(result["messages"]):
                msg_type = type(msg).__name__
                content = msg.content if hasattr(msg, 'content') else str(msg)
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    logger.info(f"  [{i}] {msg_type}: {len(msg.tool_calls)} tool calls")
                    for tc in msg.tool_calls:
                        logger.info(f"      -> {tc.get('name', 'unknown')}: {json.dumps(tc.get('args', {}), ensure_ascii=False)[:200]}")
                else:
                    logger.info(f"  [{i}] {msg_type}: {content[:150]}{'...' if len(content) > 150 else ''}")

            last_msg = result["messages"][-1]
            response_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

            logger.info(f"AI RESPONSE: {response_text[:300]}{'...' if len(response_text) > 300 else ''}")
            logger.info("=" * 60)

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
        except Exception as e:
            logger.error(f"Error invoking agent: {str(e)}", exc_info=True)
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "model": request.model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"Error: {str(e)}"
                    },
                    "finish_reason": "stop"
                }]
            }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
