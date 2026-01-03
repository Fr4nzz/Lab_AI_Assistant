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
import asyncio
import logging
import json
from typing import List, Optional, AsyncIterator, Dict, Any, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Check if claude-agent-sdk is available
CLAUDE_SDK_AVAILABLE = False
try:
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
    logger.info("[Claude] claude-agent-sdk is available")
except ImportError:
    logger.warning("[Claude] claude-agent-sdk not installed - Claude models will use Gemini fallback")


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
        model: str = "claude-opus-4-5-20250514",
        max_turns: int = 20,
        gemini_fallback: Optional[Any] = None,
    ):
        """
        Initialize the Claude Code provider.

        Args:
            model: Claude model to use (passed to Claude Code)
            max_turns: Maximum agent iterations per request
            gemini_fallback: Optional Gemini model for fallback
        """
        self.model = model
        self.max_turns = max_turns
        self.gemini_fallback = gemini_fallback
        self._is_available = None  # Cached availability check

    @property
    def is_available(self) -> bool:
        """Check if Claude Code is available and authenticated."""
        if self._is_available is not None:
            return self._is_available

        if not CLAUDE_SDK_AVAILABLE:
            self._is_available = False
            return False

        # Check if Claude Code CLI is available
        try:
            import subprocess
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            self._is_available = result.returncode == 0
            if self._is_available:
                logger.info(f"[Claude] CLI available: {result.stdout.strip()}")
            else:
                logger.warning(f"[Claude] CLI check failed: {result.stderr}")
        except Exception as e:
            logger.warning(f"[Claude] CLI not available: {e}")
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

            # Build the prompt from messages
            prompt = self._build_prompt(messages, system_prompt, context)

            # Configure Claude Code options
            options = ClaudeAgentOptions(
                max_turns=self.max_turns,
                # Don't allow dangerous tools in chat context
                allowed_tools=[],
            )

            logger.info(f"[Claude] Starting stream with {len(messages)} messages")

            # Stream from Claude Code
            async for message in query(prompt=prompt, options=options):
                async for event in self._process_message(message):
                    yield event

            # Restore API key if it was set
            if env_backup:
                os.environ["ANTHROPIC_API_KEY"] = env_backup

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

    async def _process_message(self, message) -> AsyncIterator[ClaudeEvent]:
        """Convert SDK message to our event format."""
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    yield ClaudeEvent(type="text", content=block.text)
                elif isinstance(block, ThinkingBlock):
                    yield ClaudeEvent(type="thinking", content=block.thinking)
                elif isinstance(block, ToolUseBlock):
                    yield ClaudeEvent(
                        type="tool_call",
                        tool_id=block.id,
                        tool_name=block.name,
                        tool_input=block.input
                    )
                elif isinstance(block, ToolResultBlock):
                    yield ClaudeEvent(
                        type="tool_result",
                        tool_id=block.tool_use_id,
                        tool_output=block.content
                    )
        elif isinstance(message, ResultMessage):
            yield ClaudeEvent(
                type="done",
                metadata={
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
    ) -> str:
        """
        Build a prompt string from chat messages.

        Claude Code expects a single prompt, so we format the conversation
        history in a clear way.
        """
        parts = []

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
                            text_parts.append("[IMAGE]")
                        elif part.get("type") == "media":
                            text_parts.append("[MEDIA]")
                content = "\n".join(text_parts)

            parts.append(f"\n{role}: {content}")

        return "\n".join(parts)

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


def get_claude_provider(gemini_fallback=None) -> ClaudeCodeProvider:
    """Get or create the Claude Code provider singleton."""
    global _claude_provider
    if _claude_provider is None:
        _claude_provider = ClaudeCodeProvider(gemini_fallback=gemini_fallback)
    elif gemini_fallback and _claude_provider.gemini_fallback is None:
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
