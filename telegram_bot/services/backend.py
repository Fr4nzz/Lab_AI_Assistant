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
        images: List[bytes] = None,
        audio: bytes = None,
        audio_mime: str = None,
        preprocessed_images: List[dict] = None
    ) -> list:
        """Build message content array with text, images, and audio.

        Args:
            message: Text message content
            images: List of raw image bytes (will be preprocessed server-side if preprocessed_images is None)
            audio: Audio bytes
            audio_mime: Audio MIME type
            preprocessed_images: List of already-preprocessed images from preprocess_images().
                                Each dict has: {data: base64, rotation: int, cropped: bool}
        """
        parts = []

        # Add images first
        if preprocessed_images:
            # Use preprocessed images (already rotated/cropped by YOLOE + AI pipeline)
            for i, img_data in enumerate(preprocessed_images):
                base64_img = img_data.get("data", "")
                # Preprocessed images are always JPEG
                mime_type = "image/jpeg"

                parts.append({
                    "type": "file",
                    "data": base64_img,
                    "mediaType": mime_type,
                    "url": f"data:{mime_type};base64,{base64_img}",
                    "name": f"telegram_image_{i + 1}",
                    "preprocessed": True,  # Already processed, skip server-side preprocessing
                    "rotation": img_data.get("rotation", 0),
                    "cropped": img_data.get("cropped", False)
                })
                logger.info(f"[Message] Using preprocessed image {i+1}: "
                           f"rotation={img_data.get('rotation', 0)}°, cropped={img_data.get('cropped', False)}")

        elif images:
            # Use raw images - server will preprocess them
            for i, img_bytes in enumerate(images):
                base64_img = base64.b64encode(img_bytes).decode("utf-8")
                # Detect image type
                if img_bytes[:3] == b'\xff\xd8\xff':
                    mime_type = "image/jpeg"
                elif img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                    mime_type = "image/png"
                else:
                    mime_type = "image/jpeg"  # Default

                # Use parts format for Frontend API
                # Include url for web UI display and rotationPending for server-side rotation
                parts.append({
                    "type": "file",
                    "data": base64_img,
                    "mediaType": mime_type,
                    "url": f"data:{mime_type};base64,{base64_img}",
                    "name": f"telegram_image_{i + 1}",
                    "rotationPending": True  # Let server detect and apply rotation
                })

        # Add audio (Gemini has native audio support)
        if audio:
            base64_audio = base64.b64encode(audio).decode("utf-8")
            mime = audio_mime or "audio/ogg"  # Default for Telegram voice notes
            parts.append({
                "type": "file",
                "data": base64_audio,
                "mediaType": mime,
                "url": f"data:{mime};base64,{base64_audio}",
                "name": "telegram_audio"
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
        audio: bytes = None,
        audio_mime: str = None,
        preprocessed_images: List[dict] = None,
    ) -> Tuple[str, List[str], Optional[AskUserOptions]]:
        """Send message via Frontend API and get response.

        Args:
            chat_id: Chat/thread ID
            message: User message text
            images: List of image bytes (JPEG/PNG) - used if preprocessed_images is None
            on_tool_call: Callback for tool call notifications (can be sync or async)
            model: Optional model ID to use (e.g., "gemini-3-flash-preview")
            audio: Optional audio bytes (OGG, MP3, WebM, etc.)
            audio_mime: MIME type of the audio (e.g., "audio/ogg", "audio/mpeg")
            preprocessed_images: Already-preprocessed images from preprocess_images()

        Returns:
            Tuple of (response_text, tools_used, ask_user_options)
        """
        parts = self._build_message_content(message, images, audio, audio_mime, preprocessed_images)

        if not parts:
            return "", [], None

        # Get user settings (includes enableAgentLogging)
        visitor_id = "shared"  # Sync settings with web UI
        settings = {}
        try:
            settings = await self.get_settings(visitor_id)
        except Exception as e:
            logger.warning(f"[send_message] Could not get settings: {e}")

        # Build request body for Frontend API
        request_body = {
            "messages": [{"role": "user", "parts": parts}],
            "enableAgentLogging": settings.get("enableAgentLogging", False)
        }

        # Add model if specified
        if model:
            request_body["model"] = model

        # Add media resolution if specified in settings (only for Gemini 3)
        media_resolution = settings.get("mediaResolution")
        if media_resolution and media_resolution != "unspecified":
            request_body["mediaResolution"] = media_resolution

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

    # =========================================================================
    # Prefetch Operations (for async optimization)
    # =========================================================================

    async def prefetch_orders(self) -> dict:
        """
        Prefetch orders context from backend.
        Call this when receiving an image to have orders ready.

        Returns:
            Dict with success status and freshness info
        """
        try:
            # Call backend directly for orders prefetch
            backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
            response = await self.client.post(
                f"{backend_url}/api/orders/prefetch",
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"[Prefetch] Orders prefetched: {result.get('freshness', {})}")
                return result
            else:
                logger.warning(f"[Prefetch] Failed: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"[Prefetch] Error: {e}")
            return {"success": False, "error": str(e)}

    async def detect_rotation(self, image_bytes: bytes) -> dict:
        """
        Detect image rotation using backend API.

        Args:
            image_bytes: Raw image bytes (JPEG/PNG)

        Returns:
            Dict with rotation angle and detection status
        """
        try:
            # Encode image to base64
            base64_img = base64.b64encode(image_bytes).decode("utf-8")

            # Detect mime type
            if image_bytes[:3] == b'\xff\xd8\xff':
                mime_type = "image/jpeg"
            elif image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                mime_type = "image/png"
            else:
                mime_type = "image/jpeg"

            # Call frontend API (which proxies to backend)
            response = await self.client.post(
                f"{FRONTEND_URL}/api/detect-rotation",
                json={
                    "imageBase64": base64_img,
                    "mimeType": mime_type
                },
                headers=self._headers,
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"[Rotation] Detected: {result.get('rotation', 0)}° (detected={result.get('detected', False)})")
                return result
            else:
                logger.warning(f"[Rotation] Detection failed: {response.status_code}")
                return {"rotation": 0, "detected": False}

        except Exception as e:
            logger.error(f"[Rotation] Error: {e}")
            return {"rotation": 0, "detected": False, "error": str(e)}

    async def rotate_image(self, image_bytes: bytes, rotation: int) -> bytes:
        """
        Rotate image by specified degrees.

        Args:
            image_bytes: Raw image bytes
            rotation: Rotation angle in degrees (90, 180, 270)

        Returns:
            Rotated image bytes
        """
        if rotation == 0:
            return image_bytes

        try:
            from PIL import Image
            import io

            # Load image
            img = Image.open(io.BytesIO(image_bytes))

            # Rotate (PIL uses counter-clockwise, we want clockwise)
            rotated = img.rotate(-rotation, expand=True)

            # Save to bytes
            output = io.BytesIO()
            img_format = 'JPEG' if image_bytes[:3] == b'\xff\xd8\xff' else 'PNG'
            rotated.save(output, format=img_format, quality=95)
            output.seek(0)

            logger.info(f"[Rotation] Rotated image by {rotation}°")
            return output.read()

        except ImportError:
            logger.warning("[Rotation] PIL not available, returning original image")
            return image_bytes
        except Exception as e:
            logger.error(f"[Rotation] Error rotating image: {e}")
            return image_bytes

    async def preprocess_images(self, images: List[bytes], visitor_id: str = None) -> dict:
        """
        Run full preprocessing pipeline on images (YOLOE + AI rotation/crop selection).

        This is the new unified preprocessing that should be called when images
        are received, before the user decides what to do with them.

        Args:
            images: List of image bytes (JPEG/PNG)
            visitor_id: Optional visitor ID to get user's preprocessing settings

        Returns:
            Dict with preprocessed images and metadata:
            {
                "success": True,
                "processedImages": [{"data": base64, "rotation": 270, "cropped": True}, ...],
                "choices": [{"imageIndex": 1, "rotation": 270, "useCrop": True}, ...],
                "timing": {"totalMs": 1234}
            }
        """
        if not images:
            return {"success": True, "processedImages": [], "choices": [], "timing": {"totalMs": 0}}

        try:
            import time
            start_time = time.time()

            # Get user settings for preprocessing model
            settings = {}
            if visitor_id:
                try:
                    settings = await self.get_settings(visitor_id)
                except Exception as e:
                    logger.warning(f"[Preprocess] Could not get settings: {e}")

            preprocessing_model = settings.get("preprocessingModel", "gemini-flash-latest")
            thinking_level = settings.get("preprocessingThinkingLevel", "off")

            # Prepare images for API
            image_data = []
            for i, img_bytes in enumerate(images):
                base64_img = base64.b64encode(img_bytes).decode("utf-8")

                # Detect mime type
                if img_bytes[:3] == b'\xff\xd8\xff':
                    mime_type = "image/jpeg"
                elif img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                    mime_type = "image/png"
                else:
                    mime_type = "image/jpeg"

                image_data.append({
                    "data": base64_img,
                    "mimeType": mime_type,
                    "name": f"telegram_image_{i + 1}"
                })

            # Step 1: Generate variants (rotation + YOLOE crop)
            logger.info(f"[Preprocess] Step 1: Generating variants for {len(images)} images...")
            preprocess_response = await self.client.post(
                f"{FRONTEND_URL}/api/preprocess-images",
                json={"images": image_data},
                headers=self._headers,
                timeout=60.0
            )

            if preprocess_response.status_code != 200:
                logger.warning(f"[Preprocess] Variant generation failed: {preprocess_response.status_code}")
                return {"success": False, "error": f"Variant generation failed: {preprocess_response.status_code}"}

            preprocess_result = preprocess_response.json()
            logger.info(f"[Preprocess] Generated {len(preprocess_result.get('variants', []))} variants")

            # Step 2: AI selects best rotation + crop
            logger.info(f"[Preprocess] Step 2: AI selecting rotation/crop (model: {preprocessing_model})...")
            select_response = await self.client.post(
                f"{FRONTEND_URL}/api/select-preprocessing",
                json={
                    "variants": preprocess_result.get("variants", []),
                    "labels": preprocess_result.get("labels", []),
                    "preprocessingModel": preprocessing_model,
                    "thinkingLevel": thinking_level
                },
                headers=self._headers,
                timeout=30.0
            )

            if select_response.status_code != 200:
                logger.warning(f"[Preprocess] AI selection failed: {select_response.status_code}")
                return {"success": False, "error": f"AI selection failed: {select_response.status_code}"}

            select_result = select_response.json()
            choices = select_result.get("choices", [])
            logger.info(f"[Preprocess] AI selected: {choices}")

            # Step 3: Apply the choices
            logger.info(f"[Preprocess] Step 3: Applying rotation/crop choices...")
            apply_response = await self.client.post(
                f"{FRONTEND_URL}/api/apply-preprocessing",
                json={
                    "images": image_data,
                    "choices": choices,
                    "crops": preprocess_result.get("crops", [])
                },
                headers=self._headers,
                timeout=30.0
            )

            if apply_response.status_code != 200:
                logger.warning(f"[Preprocess] Apply failed: {apply_response.status_code}")
                return {"success": False, "error": f"Apply failed: {apply_response.status_code}"}

            apply_result = apply_response.json()
            processed_images = apply_result.get("processedImages", [])

            total_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[Preprocess] Complete: {len(processed_images)} images in {total_ms}ms")

            return {
                "success": True,
                "processedImages": processed_images,
                "choices": choices,
                "timing": {"totalMs": total_ms}
            }

        except Exception as e:
            logger.error(f"[Preprocess] Error: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Settings Operations (synced with Frontend database)
    # =========================================================================

    async def get_settings(self, visitor_id: str) -> dict:
        """Get user settings from Frontend API.

        Args:
            visitor_id: Unique visitor identifier (e.g., "telegram_123456")

        Returns:
            Dict with chatModel, preprocessingModel, thinkingLevel
        """
        try:
            response = await self.client.get(
                f"{FRONTEND_URL}/api/settings",
                headers={**self._headers, "X-Visitor-Id": visitor_id}
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"[Settings] Failed to get: {response.status_code}")
                return {
                    "chatModel": "gemini-3-flash-preview",
                    "preprocessingModel": "gemini-flash-latest",
                    "thinkingLevel": "low"
                }

        except Exception as e:
            logger.error(f"[Settings] Error getting settings: {e}")
            return {
                "chatModel": "gemini-3-flash-preview",
                "preprocessingModel": "gemini-flash-latest",
                "thinkingLevel": "low"
            }

    async def update_settings(
        self,
        visitor_id: str,
        chatModel: str = None,
        preprocessingModel: str = None,
        thinkingLevel: str = None
    ) -> dict:
        """Update user settings via Frontend API.

        Args:
            visitor_id: Unique visitor identifier (e.g., "telegram_123456")
            chatModel: Optional new chat model
            preprocessingModel: Optional new preprocessing model
            thinkingLevel: Optional new thinking level

        Returns:
            Updated settings dict
        """
        try:
            body = {}
            if chatModel:
                body["chatModel"] = chatModel
            if preprocessingModel:
                body["preprocessingModel"] = preprocessingModel
            if thinkingLevel:
                body["thinkingLevel"] = thinkingLevel

            response = await self.client.post(
                f"{FRONTEND_URL}/api/settings",
                json=body,
                headers={**self._headers, "X-Visitor-Id": visitor_id}
            )

            if response.status_code == 200:
                logger.info(f"[Settings] Updated: {body}")
                return response.json()
            else:
                logger.warning(f"[Settings] Failed to update: {response.status_code}")
                return await self.get_settings(visitor_id)

        except Exception as e:
            logger.error(f"[Settings] Error updating settings: {e}")
            return await self.get_settings(visitor_id)
