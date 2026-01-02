"""Backend API service for communicating with the Lab Assistant via Frontend API."""

import os
import json
import base64
import logging
import asyncio
import inspect
from typing import List, Tuple, Optional, AsyncGenerator, Callable, Union, Awaitable
from dataclasses import dataclass

import httpx
from httpx_sse import aconnect_sse

from ..utils.tools import get_tool_display_name

logger = logging.getLogger(__name__)

# Frontend URL (handles database + proxies to backend)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Internal API key for authentication
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")


@dataclass
class StreamEvent:
    """Event from backend stream."""
    type: str  # "tool_call", "content", "done", "error"
    data: str = ""
    tool_name: str = ""


@dataclass
class AskUserOptions:
    """Options from ask_user tool for creating interactive buttons."""
    message: str
    options: List[str]


class BackendService:
    """Service for communicating with the Lab Assistant via Frontend API."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0)
        self._headers = {}
        if INTERNAL_API_KEY:
            self._headers["X-Internal-Key"] = INTERNAL_API_KEY

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    # =========================================================================
    # Chat Operations (via Frontend HTTP API)
    # =========================================================================

    async def get_recent_chats(self, limit: int = 3) -> List[Tuple[str, str]]:
        """Get recent chats from Frontend API.

        Returns:
            List of (chat_id, title) tuples
        """
        try:
            response = await self.client.get(
                f"{FRONTEND_URL}/api/chats",
                headers=self._headers
            )

            if response.status_code != 200:
                logger.error(f"Failed to get chats: {response.status_code}")
                return []

            chats = response.json()
            # Sort by createdAt descending and limit
            sorted_chats = sorted(
                chats,
                key=lambda c: c.get("createdAt", 0),
                reverse=True
            )[:limit]

            return [(c["id"], c.get("title") or "Chat sin título") for c in sorted_chats]

        except Exception as e:
            logger.error(f"Failed to get recent chats: {e}")
            return []

    async def get_chat_by_short_id(self, short_id: str) -> Optional[Tuple[str, str]]:
        """Find a chat by the beginning of its ID.

        Args:
            short_id: First 10 characters of chat ID

        Returns:
            (full_chat_id, title) or None
        """
        try:
            response = await self.client.get(
                f"{FRONTEND_URL}/api/chats",
                headers=self._headers
            )

            if response.status_code != 200:
                return None

            chats = response.json()
            for chat in chats:
                if chat["id"].startswith(short_id):
                    return (chat["id"], chat.get("title") or "Chat sin título")

            return None

        except Exception as e:
            logger.error(f"Failed to find chat: {e}")
            return None

    async def create_chat(self, title: str = "Nuevo Chat") -> Optional[str]:
        """Create a new chat via Frontend API.

        Returns:
            New chat ID or None on failure
        """
        try:
            response = await self.client.post(
                f"{FRONTEND_URL}/api/chats",
                json={"title": title},
                headers=self._headers
            )

            if response.status_code not in (200, 201):
                logger.error(f"Failed to create chat: {response.status_code} - {response.text}")
                return None

            chat = response.json()
            return chat.get("id")

        except Exception as e:
            logger.error(f"Failed to create chat: {e}")
            return None

    async def update_chat_title(self, chat_id: str, title: str) -> bool:
        """Update chat title via Frontend API.

        Returns:
            True if successful, False otherwise
        """
        try:
            response = await self.client.patch(
                f"{FRONTEND_URL}/api/chats/{chat_id}/title",
                json={"title": title},
                headers=self._headers
            )
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Failed to update chat title: {e}")
            return False

    # =========================================================================
    # Message Sending (via Frontend API which proxies to Backend)
    # =========================================================================

    def _build_message_content(
        self,
        message: str,
        images: List[bytes] = None
    ) -> list:
        """Build message content array with text and images."""
        parts = []

        # Add images first
        if images:
            for img_bytes in images:
                base64_img = base64.b64encode(img_bytes).decode("utf-8")
                # Detect image type
                if img_bytes[:3] == b'\xff\xd8\xff':
                    mime_type = "image/jpeg"
                elif img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                    mime_type = "image/png"
                else:
                    mime_type = "image/jpeg"  # Default

                # Use parts format for Frontend API
                parts.append({
                    "type": "file",
                    "data": base64_img,
                    "mediaType": mime_type
                })

        # Add text message
        if message:
            parts.append({"type": "text", "text": message})

        return parts

    async def send_message(
        self,
        chat_id: str,
        message: str,
        images: List[bytes] = None,
        on_tool_call: Callable[[str], Union[None, Awaitable[None]]] = None,
        model: str = None,
    ) -> Tuple[str, List[str], Optional[AskUserOptions]]:
        """Send message via Frontend API and get response.

        Args:
            chat_id: Chat/thread ID
            message: User message text
            images: List of image bytes (JPEG/PNG)
            on_tool_call: Callback for tool call notifications (can be sync or async)
            model: Optional model ID to use (e.g., "gemini-3-flash-preview")

        Returns:
            Tuple of (response_text, tools_used, ask_user_options)
        """
        parts = self._build_message_content(message, images)

        if not parts:
            return "", [], None

        # Build request body for Frontend API
        request_body = {
            "messages": [{"role": "user", "parts": parts}]
        }

        # Add model if specified
        if model:
            request_body["model"] = model

        tools_used = []
        response_text = ""
        ask_user_options: Optional[AskUserOptions] = None

        async def notify_tool(tool_name: str):
            """Notify about tool call, handling both sync and async callbacks."""
            if on_tool_call:
                display_name = get_tool_display_name(tool_name)
                logger.info(f"Tool call detected: {tool_name} -> {display_name}")
                try:
                    result = on_tool_call(display_name)
                    # If the callback is async, await it
                    if inspect.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.warning(f"Error in tool callback: {e}")

        try:
            logger.info(f"Sending message to chat {chat_id[:8]}...")
            async with aconnect_sse(
                self.client,
                "POST",
                f"{FRONTEND_URL}/api/chats/{chat_id}",
                json=request_body,
                headers=self._headers,
            ) as event_source:
                async for sse in event_source.aiter_sse():
                    if sse.data == "[DONE]":
                        logger.info("Stream completed")
                        break

                    try:
                        event = json.loads(sse.data)
                        event_type = event.get("type", "")

                        # Handle AI SDK protocol events
                        if event_type == "text-delta":
                            response_text += event.get("delta", "")

                        elif event_type == "tool-input-start":
                            tool_name = event.get("toolName", "")
                            if tool_name and tool_name not in tools_used:
                                tools_used.append(tool_name)
                                await notify_tool(tool_name)

                        elif event_type == "tool-output-available":
                            # Check for ask_user tool result with options
                            tool_call_id = event.get("toolCallId", "")
                            output = event.get("output", {})

                            # Check if this is ask_user based on the output structure
                            if isinstance(output, dict) and output.get("options"):
                                ask_user_options = AskUserOptions(
                                    message=output.get("message", ""),
                                    options=output.get("options", [])
                                )
                                logger.info(f"ask_user options detected: {ask_user_options.options}")

                        # Handle OpenAI format (fallback)
                        elif "choices" in event:
                            choices = event.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content_delta = delta.get("content", "")
                                if content_delta:
                                    response_text += content_delta

                                # Check for tool calls in OpenAI format
                                tool_calls = delta.get("tool_calls", [])
                                for tc in tool_calls:
                                    tool_name = tc.get("function", {}).get("name", "")
                                    if tool_name and tool_name not in tools_used:
                                        tools_used.append(tool_name)
                                        await notify_tool(tool_name)

                    except json.JSONDecodeError:
                        continue

            logger.info(f"Message complete. Tools used: {tools_used}")

        except httpx.TimeoutException:
            return "Error: Tiempo de espera agotado. El servidor tardó demasiado.", tools_used, None
        except httpx.ConnectError:
            return "Error: No se pudo conectar al servidor. Verifica que el frontend esté corriendo.", tools_used, None
        except Exception as e:
            logger.exception(f"Error sending message: {e}")
            return f"Error: {str(e)}", tools_used, None

        return response_text.strip(), tools_used, ask_user_options

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
        parts = self._build_message_content(message, images)

        if not parts:
            yield StreamEvent(type="error", data="No content to send")
            return

        request_body = {
            "messages": [{"role": "user", "parts": parts}]
        }

        seen_tools = set()

        try:
            async with aconnect_sse(
                self.client,
                "POST",
                f"{FRONTEND_URL}/api/chats/{chat_id}",
                json=request_body,
                headers=self._headers,
            ) as event_source:
                async for sse in event_source.aiter_sse():
                    if sse.data == "[DONE]":
                        yield StreamEvent(type="done")
                        return

                    try:
                        event = json.loads(sse.data)
                        event_type = event.get("type", "")

                        # Handle AI SDK protocol events
                        if event_type == "text-delta":
                            delta = event.get("delta", "")
                            if delta:
                                yield StreamEvent(type="content", data=delta)

                        elif event_type == "tool-input-start":
                            tool_name = event.get("toolName", "")
                            if tool_name and tool_name not in seen_tools:
                                seen_tools.add(tool_name)
                                yield StreamEvent(
                                    type="tool_call",
                                    tool_name=tool_name,
                                    data=get_tool_display_name(tool_name)
                                )

                        # Handle OpenAI format (fallback)
                        elif "choices" in event:
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
