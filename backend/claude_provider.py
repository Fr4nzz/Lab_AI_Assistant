"""
Claude Code Provider - Uses Max subscription via Claude Code CLI.

This provider wraps the claude-agent-sdk to invoke Claude Code programmatically.
No API key needed - uses your authenticated Claude Code installation with Max subscription.

REQUIREMENTS:
1. Claude Code CLI installed: npm install -g @anthropic-ai/claude-code
2. Authenticated with Max subscription: claude login
3. Python SDK: pip install claude-agent-sdk

USAGE:
    provider = ClaudeCodeProvider(gemini_fallback=gemini_model)
    async for event in provider.stream_chat(messages):
        print(event)
"""
import os
import sys
import asyncio
import logging
import json
import shutil
import tempfile
import base64
from typing import List, Optional, AsyncIterator, Dict, Any, Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


def find_claude_cli() -> Optional[str]:
    """
    Find the Claude CLI executable on the system.

    On Windows, npm global installs go to %APPDATA%\\npm or similar locations
    that may not be in PATH when running as a service.

    Returns the full path to claude executable, or None if not found.
    """
    # First try PATH
    claude_path = shutil.which("claude")
    if claude_path:
        return claude_path

    # Windows-specific locations
    if sys.platform == "win32":
        possible_paths = []

        # npm global install locations
        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")
        userprofile = os.environ.get("USERPROFILE", "")

        if appdata:
            possible_paths.append(Path(appdata) / "npm" / "claude.cmd")
            possible_paths.append(Path(appdata) / "npm" / "claude")

        if localappdata:
            possible_paths.append(Path(localappdata) / "npm" / "claude.cmd")
            possible_paths.append(Path(localappdata) / "npm" / "claude")
            # WinGet links
            possible_paths.append(Path(localappdata) / "Microsoft" / "WinGet" / "Links" / "claude.cmd")

        if userprofile:
            # nvm or other node version managers
            possible_paths.append(Path(userprofile) / "AppData" / "Roaming" / "npm" / "claude.cmd")

        # Program Files
        possible_paths.append(Path("C:/Program Files/nodejs/claude.cmd"))
        possible_paths.append(Path("C:/Program Files (x86)/nodejs/claude.cmd"))

        for path in possible_paths:
            if path.exists():
                return str(path)

    # macOS/Linux locations
    else:
        home = os.environ.get("HOME", "")
        if home:
            possible_paths = [
                Path(home) / ".npm-global" / "bin" / "claude",
                Path(home) / ".nvm" / "versions" / "node",  # Would need to find current version
                Path("/usr/local/bin/claude"),
                Path("/usr/bin/claude"),
            ]
            for path in possible_paths:
                if path.exists():
                    return str(path)

    return None


# Find Claude CLI at module load time
CLAUDE_CLI_PATH = find_claude_cli()

# Check if claude-agent-sdk is available
CLAUDE_SDK_AVAILABLE = False
CLAUDE_SDK_CLIENT_AVAILABLE = False
try:
    from claude_agent_sdk import query, ClaudeAgentOptions, ClaudeSDKClient
    from claude_agent_sdk.types import (
        AssistantMessage,
        TextBlock,
        ToolUseBlock,
        ToolResultBlock,
        ResultMessage,
        ThinkingBlock,
    )
    CLAUDE_SDK_AVAILABLE = True
    CLAUDE_SDK_CLIENT_AVAILABLE = True
except ImportError:
    try:
        # Fallback: try older SDK without ClaudeSDKClient
        from claude_agent_sdk import query, ClaudeAgentOptions
        from claude_agent_sdk.types import (
            AssistantMessage,
            TextBlock,
            ToolUseBlock,
            ToolResultBlock,
            ResultMessage,
            ThinkingBlock,
        )
        CLAUDE_SDK_AVAILABLE = True
    except ImportError:
        pass

# Check if MCP tools are available
MCP_TOOLS_AVAILABLE = False
try:
    from claude_mcp_tools import get_mcp_server, get_mcp_tool_names, is_mcp_available
    MCP_TOOLS_AVAILABLE = True
except ImportError:
    pass

# Log initialization status once
if CLAUDE_CLI_PATH and CLAUDE_SDK_AVAILABLE:
    features = []
    if CLAUDE_SDK_CLIENT_AVAILABLE:
        features.append("ClaudeSDKClient")
    if MCP_TOOLS_AVAILABLE:
        features.append("MCP tools")
    logger.info(f"[Claude] Ready - CLI found, SDK loaded ({', '.join(features) if features else 'query only'})")
elif not CLAUDE_CLI_PATH:
    logger.warning("[Claude] CLI not found - will use Gemini fallback")
elif not CLAUDE_SDK_AVAILABLE:
    logger.warning("[Claude] SDK not installed - will use Gemini fallback")


@dataclass
class ClaudeEvent:
    """Event emitted during Claude streaming."""
    type: str  # "text", "thinking", "tool_call", "tool_result", "done", "error"
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_id: Optional[str] = None
    tool_input: Optional[Dict] = None
    tool_output: Optional[Any] = None
    metadata: Optional[Dict] = None


class ClaudeCodeProvider:
    """
    Wraps claude-agent-sdk for use with Max subscription.
    Falls back to Gemini if Claude is unavailable or rate limited.
    """

    def __init__(
        self,
        model: str = "opus",  # Use alias - SDK maps to latest opus model
        max_turns: int = 20,
        gemini_fallback: Optional[Any] = None,
    ):
        """
        Initialize the Claude Code provider.

        Args:
            model: Claude model to use. Can be alias or full model ID:
                   - "opus" (recommended - maps to latest Opus, e.g., claude-opus-4-5-20251101)
                   - "sonnet" (maps to latest Sonnet)
                   - Or full model ID like "claude-opus-4-5-20251101"
                   Reference: https://support.claude.com/en/articles/11940350
            max_turns: Maximum agent iterations per request
            gemini_fallback: Optional Gemini model for fallback
        """
        self.model = model
        self.max_turns = max_turns
        self.gemini_fallback = gemini_fallback
        self._is_available = None  # Cached availability check
        self._cli_path = CLAUDE_CLI_PATH

    @property
    def is_available(self) -> bool:
        """Check if Claude Code is available and authenticated."""
        if self._is_available is not None:
            return self._is_available

        if not CLAUDE_SDK_AVAILABLE:
            self._is_available = False
            return False

        if not self._cli_path:
            self._is_available = False
            return False

        # Check if Claude Code CLI works
        try:
            import subprocess
            result = subprocess.run(
                [self._cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=(sys.platform == "win32")  # Use shell on Windows for .cmd files
            )
            self._is_available = result.returncode == 0
            if not self._is_available:
                logger.warning(f"[Claude] CLI check failed: {result.stderr.strip()}")
        except Exception as e:
            logger.warning(f"[Claude] CLI error: {e}")
            self._is_available = False

        return self._is_available

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
    ) -> AsyncIterator[ClaudeEvent]:
        """
        Stream a chat response from Claude Code.

        Args:
            messages: List of chat messages in OpenAI format
            system_prompt: Optional system prompt to prepend
            context: Optional context (orders, tabs, etc.)

        Yields:
            ClaudeEvent objects representing stream events
        """
        if not self.is_available:
            logger.warning("[Claude] Not available, using Gemini fallback")
            async for event in self._gemini_fallback_stream(messages, system_prompt, context):
                yield event
            return

        try:
            # Remove any ANTHROPIC_API_KEY to force subscription auth
            env_backup = os.environ.get("ANTHROPIC_API_KEY")
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]

            # Set ANTHROPIC_MODEL at process level to force model selection
            # Reference: https://code.claude.com/docs/en/model-config
            # Priority: 1. /model command, 2. --model flag, 3. ANTHROPIC_MODEL env, 4. settings.json
            model_backup = os.environ.get("ANTHROPIC_MODEL")
            os.environ["ANTHROPIC_MODEL"] = self.model
            logger.info(f"[Claude] Set ANTHROPIC_MODEL={self.model} (was: {model_backup})")

            # Build the prompt from messages (saves images to temp files)
            prompt, temp_image_paths = self._build_prompt(messages, system_prompt, context)
            has_images = len(temp_image_paths) > 0

            if has_images:
                logger.info(f"[Claude] Prompt includes {len(temp_image_paths)} image(s)")

            try:
                # Check if we can use ClaudeSDKClient with MCP tools
                use_mcp_tools = CLAUDE_SDK_CLIENT_AVAILABLE and MCP_TOOLS_AVAILABLE and is_mcp_available()

                if use_mcp_tools:
                    # Use ClaudeSDKClient with MCP tools (lab tools)
                    async for event in self._stream_with_mcp_tools(prompt, has_images):
                        yield event
                else:
                    # Fallback to query() without custom tools
                    logger.warning("[Claude] MCP tools not available, using query() without tools")
                    async for event in self._stream_with_query(prompt):
                        yield event
            finally:
                # Clean up temp image files
                for temp_path in temp_image_paths:
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                            logger.debug(f"[Claude] Cleaned up temp image: {temp_path}")
                    except Exception as e:
                        logger.warning(f"[Claude] Failed to clean up temp image {temp_path}: {e}")

            # Restore API key if it was set
            if env_backup:
                os.environ["ANTHROPIC_API_KEY"] = env_backup

            # Restore ANTHROPIC_MODEL
            if model_backup:
                os.environ["ANTHROPIC_MODEL"] = model_backup
            elif "ANTHROPIC_MODEL" in os.environ:
                del os.environ["ANTHROPIC_MODEL"]

        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"[Claude] Error: {e}")

            # Check if it's a rate limit error
            if "rate limit" in error_str or "quota" in error_str or "capacity" in error_str:
                logger.warning("[Claude] Rate limit hit, falling back to Gemini")
                yield ClaudeEvent(type="error", content=f"Claude rate limited: {e}")
                async for event in self._gemini_fallback_stream(messages, system_prompt, context):
                    yield event
            else:
                yield ClaudeEvent(type="error", content=str(e))

    async def _stream_with_mcp_tools(self, prompt: str, has_images: bool = False) -> AsyncIterator[ClaudeEvent]:
        """
        Stream using ClaudeSDKClient with MCP tools.

        This enables Claude to use the lab tools (search_orders, edit_results, etc.)
        instead of built-in tools like Bash.

        Args:
            prompt: The formatted prompt string
            has_images: If True, adds "Read" tool to allowed_tools so Claude can view image files
        """
        mcp_server = get_mcp_server()
        mcp_tool_names = get_mcp_tool_names()

        # Build allowed tools list
        allowed_tools = list(mcp_tool_names)  # Copy the list
        if has_images:
            # Add built-in Read tool so Claude can view image files
            allowed_tools.append("Read")
            logger.info(f"[Claude] Added Read tool for image viewing")

        logger.info(f"[Claude] Starting with model={self.model}, {len(allowed_tools)} tools (images={has_images})")
        logger.debug(f"[Claude] Prompt ({len(prompt)} chars)")

        # Configure options with MCP server, model, and streaming
        # Reference: https://github.com/anthropics/claude-agent-sdk-python
        # Note: We set both model parameter AND env ANTHROPIC_MODEL to ensure
        # the correct model is used. Some Max subscription users have reported
        # issues where the model parameter alone doesn't work.
        # See: https://github.com/anthropics/claude-code/issues/6247
        options = ClaudeAgentOptions(
            model=self.model,  # Specify model (opus, sonnet, etc.)
            max_turns=self.max_turns,
            mcp_servers={"lab": mcp_server},
            # Allow our MCP tools + Read for images when needed
            allowed_tools=allowed_tools,
            # Enable streaming of partial messages for real-time updates
            # Reference: https://github.com/anthropics/claude-agent-sdk-python/issues/164
            include_partial_messages=True,
            # Set ANTHROPIC_MODEL env var to ensure correct model is used
            # This helps bypass subscription tier detection issues
            env={"ANTHROPIC_MODEL": self.model},
        )

        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)

                message_count = 0
                model_used = None  # Track model from AssistantMessage
                pending_tool_calls = {}  # Track tool calls awaiting results: id -> name

                async for message in client.receive_response():
                    message_count += 1
                    logger.debug(f"[Claude] Message {message_count}: {type(message).__name__}")

                    # Capture model from first AssistantMessage
                    if isinstance(message, AssistantMessage) and model_used is None:
                        model_used = getattr(message, 'model', None)
                        if model_used:
                            logger.info(f"[Claude] Model confirmed: {model_used}")

                    async for event in self._process_message(message, model_used, pending_tool_calls):
                        yield event

                # Emit synthetic results for any pending tool calls that didn't get results
                for tool_id, tool_name in list(pending_tool_calls.items()):
                    logger.info(f"[Claude] Emitting synthetic result for {tool_name} ({tool_id})")
                    yield ClaudeEvent(
                        type="tool_result",
                        tool_id=tool_id,
                        tool_output={"status": "completed"}
                    )

                logger.info(f"[Claude] Complete ({message_count} messages, model={model_used})")

        except Exception as e:
            logger.error(f"[Claude] ClaudeSDKClient error: {e}", exc_info=True)
            raise

    async def _stream_with_query(self, prompt: str) -> AsyncIterator[ClaudeEvent]:
        """
        Stream using query() without custom tools (fallback).

        This is used when ClaudeSDKClient or MCP tools are not available.
        """
        options = ClaudeAgentOptions(
            model=self.model,
            max_turns=self.max_turns,
            # Don't allow any tools in fallback mode
            allowed_tools=[],
            include_partial_messages=True,
            # Set ANTHROPIC_MODEL env var to ensure correct model is used
            env={"ANTHROPIC_MODEL": self.model},
        )

        logger.info(f"[Claude] Using query() with model={self.model} (no MCP tools)")

        async for message in query(prompt=prompt, options=options):
            async for event in self._process_message(message):
                yield event

    async def _process_message(self, message, model_used: str = None, pending_tool_calls: dict = None) -> AsyncIterator[ClaudeEvent]:
        """Convert SDK message to our event format."""
        if pending_tool_calls is None:
            pending_tool_calls = {}

        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    # Before emitting text, emit synthetic results for pending tools
                    # (since text after a tool call means the tool completed)
                    for tool_id, tool_name in list(pending_tool_calls.items()):
                        logger.info(f"[Claude] Auto-completing tool {tool_name} ({tool_id}) before text")
                        yield ClaudeEvent(
                            type="tool_result",
                            tool_id=tool_id,
                            tool_output={"status": "completed"}
                        )
                        del pending_tool_calls[tool_id]

                    # Log text responses
                    text_preview = block.text[:200] + "..." if len(block.text) > 200 else block.text
                    logger.info(f"[Claude] TEXT: {text_preview}")
                    yield ClaudeEvent(type="text", content=block.text)
                elif isinstance(block, ThinkingBlock):
                    logger.info(f"[Claude] THINKING: {block.thinking[:100]}...")
                    yield ClaudeEvent(type="thinking", content=block.thinking)
                elif isinstance(block, ToolUseBlock):
                    # Track this tool call as pending
                    pending_tool_calls[block.id] = block.name

                    # Log tool calls with full input for debugging
                    input_str = json.dumps(block.input, ensure_ascii=False, indent=2)
                    logger.info(f"[Claude] TOOL CALL: {block.name} ({block.id})")
                    logger.info(f"[Claude] TOOL INPUT:\n{input_str}")
                    yield ClaudeEvent(
                        type="tool_call",
                        tool_id=block.id,
                        tool_name=block.name,
                        tool_input=block.input
                    )
                elif isinstance(block, ToolResultBlock):
                    # Remove from pending since we got the actual result
                    pending_tool_calls.pop(block.tool_use_id, None)

                    # Log tool results
                    result_str = str(block.content)[:500] if block.content else "None"
                    logger.info(f"[Claude] TOOL RESULT ({block.tool_use_id}): {result_str}")
                    yield ClaudeEvent(
                        type="tool_result",
                        tool_id=block.tool_use_id,
                        tool_output=block.content
                    )
        elif isinstance(message, ResultMessage):
            # Log completion - model_used is passed from AssistantMessage
            logger.info(f"[Claude] DONE: model={model_used}, turns={getattr(message, 'num_turns', '?')}, duration={getattr(message, 'duration_ms', '?')}ms")

            yield ClaudeEvent(
                type="done",
                metadata={
                    "model": model_used,
                    "duration_ms": getattr(message, "duration_ms", None),
                    "num_turns": getattr(message, "num_turns", None),
                    "session_id": getattr(message, "session_id", None),
                    "total_cost_usd": getattr(message, "total_cost_usd", 0),  # $0 with Max
                }
            )

    def _build_prompt(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        context: Optional[str] = None
    ) -> tuple[str, List[str]]:
        """
        Build a prompt string from chat messages.

        Claude Code expects a single prompt, so we format the conversation
        history in a clear way. Images are saved to temp files and referenced by path.

        Returns:
            tuple: (prompt_string, list_of_temp_image_paths)
        """
        parts = []
        temp_image_paths = []

        # Add system prompt if provided
        if system_prompt:
            parts.append(f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n")

        # Add context if provided
        if context:
            parts.append(f"CURRENT CONTEXT:\n{context}\n")

        # Add conversation history
        parts.append("CONVERSATION:")
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")

            # Handle multimodal content
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                        elif part.get("type") == "image_url":
                            # Save image to temp file for Claude to read
                            image_path = self._save_image_to_temp(part.get("image_url", {}))
                            if image_path:
                                temp_image_paths.append(image_path)
                                text_parts.append(f"[Image saved to: {image_path}]\nPlease use the Read tool to view this image.")
                            else:
                                text_parts.append("[IMAGE - failed to save]")
                        elif part.get("type") == "media":
                            # Handle media content (usually base64 images)
                            media_type = part.get("mimeType", "")
                            if media_type.startswith("image/"):
                                image_path = self._save_base64_image(part.get("data", ""), media_type)
                                if image_path:
                                    temp_image_paths.append(image_path)
                                    text_parts.append(f"[Image saved to: {image_path}]\nPlease use the Read tool to view this image.")
                                else:
                                    text_parts.append("[IMAGE - failed to save]")
                            else:
                                text_parts.append("[MEDIA]")
                content = "\n".join(text_parts)

            parts.append(f"\n{role}: {content}")

        return "\n".join(parts), temp_image_paths

    def _save_image_to_temp(self, image_url_data: Dict[str, Any]) -> Optional[str]:
        """
        Save an image from URL or base64 data to a temp file.

        Args:
            image_url_data: Dict with 'url' key (can be data URL or http URL)

        Returns:
            Path to saved temp file, or None if failed
        """
        try:
            url = image_url_data.get("url", "")
            if not url:
                return None

            # Handle data URLs (base64 encoded)
            if url.startswith("data:"):
                # Format: data:image/png;base64,<data>
                parts = url.split(",", 1)
                if len(parts) != 2:
                    return None

                header = parts[0]  # e.g., "data:image/png;base64"
                data = parts[1]

                # Extract mime type
                if "image/png" in header:
                    ext = ".png"
                elif "image/jpeg" in header or "image/jpg" in header:
                    ext = ".jpg"
                elif "image/gif" in header:
                    ext = ".gif"
                elif "image/webp" in header:
                    ext = ".webp"
                else:
                    ext = ".png"  # Default

                return self._save_base64_image(data, f"image/{ext[1:]}")

            # Handle HTTP URLs - would need to download
            # For now, just return None (not supported)
            logger.warning(f"[Claude] HTTP image URLs not yet supported: {url[:50]}...")
            return None

        except Exception as e:
            logger.error(f"[Claude] Failed to save image: {e}")
            return None

    def _save_base64_image(self, data: str, mime_type: str) -> Optional[str]:
        """
        Save base64 image data to a temp file.

        Args:
            data: Base64 encoded image data
            mime_type: MIME type (e.g., "image/png")

        Returns:
            Path to saved temp file, or None if failed
        """
        try:
            # Determine extension
            if "png" in mime_type:
                ext = ".png"
            elif "jpeg" in mime_type or "jpg" in mime_type:
                ext = ".jpg"
            elif "gif" in mime_type:
                ext = ".gif"
            elif "webp" in mime_type:
                ext = ".webp"
            else:
                ext = ".png"

            # Decode and save
            image_data = base64.b64decode(data)

            # Create temp file
            fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="claude_image_")
            with os.fdopen(fd, 'wb') as f:
                f.write(image_data)

            # Try to get image dimensions for debugging
            try:
                from PIL import Image
                import io
                with Image.open(io.BytesIO(image_data)) as img:
                    width, height = img.size
                    logger.info(f"[Claude] Saved image to temp file: {temp_path} ({len(image_data)} bytes, {width}x{height}px)")
            except ImportError:
                logger.info(f"[Claude] Saved image to temp file: {temp_path} ({len(image_data)} bytes)")
            except Exception as e:
                logger.info(f"[Claude] Saved image to temp file: {temp_path} ({len(image_data)} bytes, dimensions unknown: {e})")
            return temp_path

        except Exception as e:
            logger.error(f"[Claude] Failed to save base64 image: {e}")
            return None

    async def _gemini_fallback_stream(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
    ) -> AsyncIterator[ClaudeEvent]:
        """Fallback to Gemini when Claude is unavailable."""
        if not self.gemini_fallback:
            yield ClaudeEvent(
                type="error",
                content="Claude is unavailable and no Gemini fallback configured"
            )
            return

        yield ClaudeEvent(
            type="text",
            content="*[Using Gemini fallback - Claude unavailable]*\n\n"
        )

        try:
            # Convert messages to LangChain format
            from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

            lc_messages = []
            if system_prompt:
                lc_messages.append(SystemMessage(content=system_prompt))
            if context:
                lc_messages.append(SystemMessage(content=f"Context:\n{context}"))

            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if isinstance(content, list):
                    # Handle multimodal - extract text only for fallback
                    text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                    content = "\n".join(text_parts)

                if role == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))

            # Invoke Gemini
            response = await self.gemini_fallback.ainvoke(lc_messages)
            yield ClaudeEvent(type="text", content=response.content)
            yield ClaudeEvent(type="done", metadata={"fallback": True, "model": "gemini"})

        except Exception as e:
            logger.error(f"[Claude] Gemini fallback also failed: {e}")
            yield ClaudeEvent(type="error", content=f"Both Claude and Gemini failed: {e}")


# Singleton instance (created on first import)
_claude_provider: Optional[ClaudeCodeProvider] = None


def get_claude_provider(gemini_fallback=None, model: str = None) -> ClaudeCodeProvider:
    """
    Get or create the Claude Code provider singleton.

    Args:
        gemini_fallback: Optional Gemini model for fallback
        model: Model alias or full ID (e.g., "opus", "sonnet", or "claude-opus-4-5-20251101")
               This can be changed per-request.
    """
    global _claude_provider
    if _claude_provider is None:
        _claude_provider = ClaudeCodeProvider(
            model=model or "opus",  # Use alias - maps to latest Opus model
            gemini_fallback=gemini_fallback
        )
    else:
        # Update model if specified (allows changing model per request)
        if model:
            _claude_provider.model = model
        if gemini_fallback and _claude_provider.gemini_fallback is None:
            _claude_provider.gemini_fallback = gemini_fallback
    return _claude_provider


def check_claude_code_status() -> Dict[str, Any]:
    """
    Check Claude Code installation and authentication status.

    Returns dict with:
        - installed: bool - Is Claude Code CLI installed?
        - authenticated: bool - Is user authenticated?
        - version: str - Claude Code version
        - subscription: str - Subscription type (if authenticated)
        - error: str - Error message if any
    """
    result = {
        "installed": False,
        "authenticated": False,
        "version": None,
        "subscription": None,
        "error": None
    }

    try:
        import subprocess

        # Check if installed
        version_result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if version_result.returncode == 0:
            result["installed"] = True
            result["version"] = version_result.stdout.strip()

            # Check authentication by running a simple query
            # This will fail if not authenticated
            auth_result = subprocess.run(
                ["claude", "-p", "Say OK", "--max-turns", "1", "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "ANTHROPIC_API_KEY": ""}  # Force subscription auth
            )

            if auth_result.returncode == 0:
                result["authenticated"] = True
                result["subscription"] = "Max"  # Assume Max if working without API key
            else:
                result["error"] = "Not authenticated. Run 'claude login' to authenticate."
        else:
            result["error"] = "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"

    except FileNotFoundError:
        result["error"] = "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
    except subprocess.TimeoutExpired:
        result["error"] = "Claude Code timed out - may not be authenticated"
    except Exception as e:
        result["error"] = str(e)

    return result
