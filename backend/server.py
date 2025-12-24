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

    # Extract initial orders context
    initial_orders_context = await extract_initial_context()
    if initial_orders_context:
        logger.info(f"Extracted initial context with {initial_orders_context.count('|') // 8} orders")

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
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # Extract the last user message
    last_user_message = None
    for msg in reversed(request.messages):
        if msg["role"] == "user":
            last_user_message = msg["content"]
            break

    if not last_user_message:
        logger.error("No user message found in request")
        return {"error": "No user message found"}

    logger.info("=" * 60)
    logger.info(f"USER MESSAGE: {last_user_message[:200]}{'...' if len(last_user_message) > 200 else ''}")
    logger.info(f"Thread ID: {thread_id}, Stream: {request.stream}")

    if request.stream:
        async def generate():
            full_response = []
            try:
                # Check if this is a new thread (no existing messages)
                existing_state = await graph.aget_state(config)
                is_first_message = not existing_state.values.get("messages")

                # Only include context on first message of thread
                initial_state = {"messages": [HumanMessage(content=last_user_message)]}
                if is_first_message and initial_orders_context:
                    initial_state["current_page_context"] = initial_orders_context
                    logger.info("[Chat] First message - including orders context")

                async for event in graph.astream_events(
                    initial_state,
                    config,
                    version="v2"
                ):
                    event_type = event.get("event", "")

                    # Log tool calls
                    if event_type == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_input = event.get("data", {}).get("input", {})
                        logger.info(f"TOOL CALL: {tool_name}")
                        logger.debug(f"  Input: {json.dumps(tool_input, ensure_ascii=False)[:500]}")

                    elif event_type == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        tool_output = event.get("data", {}).get("output", "")
                        logger.info(f"TOOL RESULT: {tool_name}")
                        logger.debug(f"  Output: {str(tool_output)[:500]}")

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
                                    "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                                    "object": "chat.completion.chunk",
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
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"Stream error: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    else:
        try:
            # Check if this is a new thread (no existing messages)
            existing_state = await graph.aget_state(config)
            is_first_message = not existing_state.values.get("messages")

            # Only include context on first message of thread
            initial_state = {"messages": [HumanMessage(content=last_user_message)]}
            if is_first_message and initial_orders_context:
                initial_state["current_page_context"] = initial_orders_context
                logger.info("[Chat] First message - including orders context")

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
