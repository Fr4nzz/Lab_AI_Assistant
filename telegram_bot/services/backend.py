"""Backend API service for communicating with the Lab Assistant backend."""

import os
import json
import base64
import logging
import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional, AsyncGenerator, Callable
from dataclasses import dataclass

import httpx

from ..utils.tools import get_tool_display_name

logger = logging.getLogger(__name__)

# Backend URL
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# Database path (same as web UI)
DB_PATH = Path(__file__).parent.parent.parent / "data" / "lab-assistant.db"


@dataclass
class StreamEvent:
    """Event from backend stream."""
    type: str  # "tool_call", "content", "done", "error"
    data: str = ""
    tool_name: str = ""


class BackendService:
    """Service for communicating with the Lab Assistant backend."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    # =========================================================================
    # Database Operations (Direct SQLite access for speed)
    # =========================================================================

    def get_recent_chats(self, limit: int = 3) -> List[Tuple[str, str]]:
        """Get recent chats from database.

        Returns:
            List of (chat_id, title) tuples
        """
        if not DB_PATH.exists():
            return []

        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.execute(
                "SELECT id, title FROM chats ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            chats = [(row[0], row[1] or "Chat sin título") for row in cursor.fetchall()]
            conn.close()
            return chats
        except Exception as e:
            logger.error(f"Failed to get recent chats: {e}")
            return []

    def get_chat_by_short_id(self, short_id: str) -> Optional[Tuple[str, str]]:
        """Find a chat by the beginning of its ID.

        Args:
            short_id: First 10 characters of chat ID

        Returns:
            (full_chat_id, title) or None
        """
        if not DB_PATH.exists():
            return None

        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.execute(
                "SELECT id, title FROM chats WHERE id LIKE ? LIMIT 1",
                (f"{short_id}%",)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return (row[0], row[1] or "Chat sin título")
            return None
        except Exception as e:
            logger.error(f"Failed to find chat: {e}")
            return None

    def create_chat(self, title: str = "Nuevo Chat") -> Optional[str]:
        """Create a new chat in database.

        Returns:
            New chat ID or None on failure
        """
        import uuid
        from datetime import datetime

        if not DB_PATH.parent.exists():
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        try:
            chat_id = str(uuid.uuid4())
            now = int(datetime.now().timestamp() * 1000)

            conn = sqlite3.connect(str(DB_PATH))
            conn.execute(
                "INSERT INTO chats (id, title, created_at) VALUES (?, ?, ?)",
                (chat_id, title, now)
            )
            conn.commit()
            conn.close()
            return chat_id
        except Exception as e:
            logger.error(f"Failed to create chat: {e}")
            return None

    def update_chat_title(self, chat_id: str, title: str):
        """Update chat title."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute(
                "UPDATE chats SET title = ? WHERE id = ?",
                (title, chat_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update chat title: {e}")

    # =========================================================================
    # Backend API Communication
    # =========================================================================

    async def send_message(
        self,
        chat_id: str,
        message: str,
        images: List[bytes] = None,
        on_tool_call: Callable[[str], None] = None,
    ) -> Tuple[str, List[str]]:
        """Send message to backend and get response.

        Args:
            chat_id: Chat/thread ID
            message: User message text
            images: List of image bytes (JPEG/PNG)
            on_tool_call: Callback for tool call notifications

        Returns:
            Tuple of (response_text, tools_used)
        """
        # Build message content
        content = []

        # Add images first
        if images:
            for img_bytes in images:
                base64_img = base64.b64encode(img_bytes).decode("utf-8")
                # Detect image type (simple check)
                if img_bytes[:3] == b'\xff\xd8\xff':
                    mime_type = "image/jpeg"
                elif img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                    mime_type = "image/png"
                else:
                    mime_type = "image/jpeg"  # Default

                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64_img}"}
                })

        # Add text message
        if message:
            content.append({"type": "text", "text": message})

        # If no content, return empty
        if not content:
            return "", []

        # Build request
        request_body = {
            "messages": [{"role": "user", "content": content}],
            "stream": True,
            "model": os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        }

        # Send request with streaming
        tools_used = []
        response_text = ""

        try:
            async with self.client.stream(
                "POST",
                f"{BACKEND_URL}/api/v1/chat/completions",
                json=request_body,
                headers={"x-thread-id": chat_id},
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"Backend error {response.status_code}: {error_text}")
                    return f"Error del servidor: {response.status_code}", []

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break

                    try:
                        event = json.loads(data)
                        event_type = event.get("type", "")

                        # Handle tool calls
                        if event_type == "tool_call" or "tool_calls" in event:
                            tool_info = event.get("tool_calls", [{}])[0] if "tool_calls" in event else event
                            tool_name = tool_info.get("function", {}).get("name") or tool_info.get("name", "")
                            if tool_name and tool_name not in tools_used:
                                tools_used.append(tool_name)
                                if on_tool_call:
                                    display_name = get_tool_display_name(tool_name)
                                    on_tool_call(display_name)

                        # Handle content delta (OpenAI format)
                        choices = event.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content_delta = delta.get("content", "")
                            if content_delta:
                                response_text += content_delta

                        # Handle direct content
                        if event_type == "content":
                            response_text += event.get("text", "")

                    except json.JSONDecodeError:
                        continue

        except httpx.TimeoutException:
            return "Error: Tiempo de espera agotado. El servidor tardó demasiado.", tools_used
        except httpx.ConnectError:
            return "Error: No se pudo conectar al servidor. Verifica que el backend esté corriendo.", tools_used
        except Exception as e:
            logger.exception(f"Error sending message: {e}")
            return f"Error: {str(e)}", tools_used

        return response_text.strip(), tools_used

    async def send_message_stream(
        self,
        chat_id: str,
        message: str,
        images: List[bytes] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Send message and yield stream events.

        Yields:
            StreamEvent objects for tool calls, content, and completion
        """
        # Build message content
        content = []

        if images:
            for img_bytes in images:
                base64_img = base64.b64encode(img_bytes).decode("utf-8")
                mime_type = "image/jpeg" if img_bytes[:3] == b'\xff\xd8\xff' else "image/png"
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64_img}"}
                })

        if message:
            content.append({"type": "text", "text": message})

        if not content:
            yield StreamEvent(type="error", data="No content to send")
            return

        request_body = {
            "messages": [{"role": "user", "content": content}],
            "stream": True,
            "model": os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        }

        try:
            async with self.client.stream(
                "POST",
                f"{BACKEND_URL}/api/v1/chat/completions",
                json=request_body,
                headers={"x-thread-id": chat_id},
            ) as response:
                if response.status_code != 200:
                    yield StreamEvent(type="error", data=f"Server error: {response.status_code}")
                    return

                seen_tools = set()

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data = line[6:]
                    if data == "[DONE]":
                        yield StreamEvent(type="done")
                        return

                    try:
                        event = json.loads(data)

                        # Check for tool calls
                        if "tool_calls" in event or event.get("type") == "tool_call":
                            tool_info = event.get("tool_calls", [{}])[0] if "tool_calls" in event else event
                            tool_name = tool_info.get("function", {}).get("name") or tool_info.get("name", "")
                            if tool_name and tool_name not in seen_tools:
                                seen_tools.add(tool_name)
                                yield StreamEvent(
                                    type="tool_call",
                                    tool_name=tool_name,
                                    data=get_tool_display_name(tool_name)
                                )

                        # Check for content
                        choices = event.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content_delta = delta.get("content", "")
                            if content_delta:
                                yield StreamEvent(type="content", data=content_delta)

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            yield StreamEvent(type="error", data=str(e))
