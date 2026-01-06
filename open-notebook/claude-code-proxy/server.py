"""
Claude Code Proxy Server

Exposes Claude Code (Max subscription) as an OpenAI-compatible API.
This allows applications like Open Notebook to use Claude via Claude Code.

Usage:
    python server.py

    Then set in Open Notebook:
    OPENAI_COMPATIBLE_BASE_URL=http://localhost:8080/v1
    OPENAI_COMPATIBLE_API_KEY=dummy-key
"""

import asyncio
import os
import time
import uuid
import logging
from typing import List, Optional, Dict, Any, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check SDK availability
CLAUDE_SDK_AVAILABLE = False
try:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
    CLAUDE_SDK_AVAILABLE = True
    logger.info("Claude Agent SDK loaded successfully")
except ImportError as e:
    logger.warning(f"Claude Agent SDK not available: {e}")

# Configuration
DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "sonnet")  # sonnet or opus
MAX_TURNS = int(os.getenv("CLAUDE_MAX_TURNS", "1"))
PORT = int(os.getenv("PORT", "8080"))


# --- OpenAI-compatible Request/Response Models ---

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str = "gpt-4"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    stream: Optional[bool] = False
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[List[str]] = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "claude-code"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]


# --- Claude Code Integration ---

async def query_claude_code(messages: List[ChatMessage], model: str = DEFAULT_MODEL) -> str:
    """Query Claude Code using the Agent SDK."""
    if not CLAUDE_SDK_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Claude Agent SDK not available. Install with: pip install claude-agent-sdk"
        )

    # Convert messages to a single prompt
    # Claude Code expects a single query, so we'll format the conversation
    prompt_parts = []
    for msg in messages:
        if msg.role == "system":
            prompt_parts.append(f"[System Instructions]: {msg.content}")
        elif msg.role == "user":
            prompt_parts.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            prompt_parts.append(f"Assistant: {msg.content}")

    # Add instruction for the assistant to continue
    if messages and messages[-1].role == "user":
        prompt_parts.append("Assistant:")

    full_prompt = "\n\n".join(prompt_parts)

    # Map model names to Claude models
    claude_model = model.lower()
    if "opus" in claude_model or "gpt-4" in claude_model:
        claude_model = "opus"
    elif "sonnet" in claude_model or "gpt-3.5" in claude_model:
        claude_model = "sonnet"
    else:
        claude_model = DEFAULT_MODEL

    logger.info(f"Querying Claude Code with model: {claude_model}")

    options = ClaudeAgentOptions(
        model=claude_model,
        max_turns=MAX_TURNS,
        allowed_tools=[],  # Disable tools for simple chat
    )

    response_text = ""

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(full_prompt)

            async for message in client.receive_response():
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            response_text += block.text
    except Exception as e:
        logger.error(f"Claude Code error: {e}")
        raise HTTPException(status_code=500, detail=f"Claude Code error: {str(e)}")

    return response_text.strip()


async def stream_claude_code(messages: List[ChatMessage], model: str = DEFAULT_MODEL) -> AsyncIterator[str]:
    """Stream responses from Claude Code in SSE format."""
    if not CLAUDE_SDK_AVAILABLE:
        yield 'data: {"error": "Claude Agent SDK not available"}\n\n'
        return

    # Convert messages to prompt (same as above)
    prompt_parts = []
    for msg in messages:
        if msg.role == "system":
            prompt_parts.append(f"[System Instructions]: {msg.content}")
        elif msg.role == "user":
            prompt_parts.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            prompt_parts.append(f"Assistant: {msg.content}")

    if messages and messages[-1].role == "user":
        prompt_parts.append("Assistant:")

    full_prompt = "\n\n".join(prompt_parts)

    # Map model
    claude_model = model.lower()
    if "opus" in claude_model or "gpt-4" in claude_model:
        claude_model = "opus"
    elif "sonnet" in claude_model or "gpt-3.5" in claude_model:
        claude_model = "sonnet"
    else:
        claude_model = DEFAULT_MODEL

    request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

    options = ClaudeAgentOptions(
        model=claude_model,
        max_turns=MAX_TURNS,
        allowed_tools=[],
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(full_prompt)

            async for message in client.receive_response():
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text') and block.text:
                            # Send chunk in OpenAI streaming format
                            chunk = {
                                "id": request_id,
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": block.text},
                                    "finish_reason": None
                                }]
                            }
                            yield f"data: {JSONResponse(content=chunk).body.decode()}\n\n"

        # Send final chunk
        final_chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {JSONResponse(content=final_chunk).body.decode()}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f'data: {{"error": "{str(e)}"}}\n\n'


# --- FastAPI App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Claude Code Proxy starting on port {PORT}")
    logger.info(f"Default model: {DEFAULT_MODEL}")
    logger.info(f"SDK available: {CLAUDE_SDK_AVAILABLE}")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Claude Code Proxy",
    description="OpenAI-compatible API proxy for Claude Code (Max subscription)",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "sdk_available": CLAUDE_SDK_AVAILABLE,
        "default_model": DEFAULT_MODEL
    }


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible endpoint)."""
    models = [
        ModelInfo(id="claude-sonnet", created=int(time.time())),
        ModelInfo(id="claude-opus", created=int(time.time())),
        ModelInfo(id="gpt-4", created=int(time.time())),  # Alias for opus
        ModelInfo(id="gpt-3.5-turbo", created=int(time.time())),  # Alias for sonnet
    ]
    return ModelsResponse(data=models)


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """Chat completions endpoint (OpenAI-compatible)."""
    logger.info(f"Chat request: model={request.model}, messages={len(request.messages)}, stream={request.stream}")

    if request.stream:
        return StreamingResponse(
            stream_claude_code(request.messages, request.model),
            media_type="text/event-stream"
        )

    # Non-streaming response
    response_text = await query_claude_code(request.messages, request.model)

    # Estimate tokens (rough approximation)
    prompt_tokens = sum(len(m.content.split()) * 1.3 for m in request.messages)
    completion_tokens = len(response_text.split()) * 1.3

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
        created=int(time.time()),
        model=request.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=response_text),
                finish_reason="stop"
            )
        ],
        usage=Usage(
            prompt_tokens=int(prompt_tokens),
            completion_tokens=int(completion_tokens),
            total_tokens=int(prompt_tokens + completion_tokens)
        )
    )


# Legacy endpoint for compatibility
@app.post("/chat/completions")
async def chat_completions_legacy(request: ChatCompletionRequest):
    """Legacy chat completions endpoint (without /v1 prefix)."""
    return await chat_completions(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
