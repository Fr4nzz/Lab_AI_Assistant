"""
AI SDK UI Message Stream Protocol v1 Adapter.

Converts LangGraph events to AI SDK v6 UI Message Stream Protocol format.
Documentation: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol

Stream Format (SSE) - Supported by @ai-sdk/vue Chat class:
- data: {"type":"text-delta","textDelta":"content"}
- data: {"type":"error","error":"message"}
- data: {"type":"finish","finishReason":"stop","usage":{}}
- data: [DONE]

Note: The Chat class validates event types strictly. Only text-delta, error,
and finish are supported. Tool calls are shown as formatted text.
"""
import json
import uuid
from typing import Any, Optional


class StreamAdapter:
    """Converts LangGraph events to AI SDK v6 UI Message Stream Protocol"""

    def __init__(self):
        self.message_id = f"msg_{uuid.uuid4().hex[:12]}"
        self.current_step = 0

    def _sse(self, data: Any) -> str:
        """Format data as SSE event"""
        if isinstance(data, str):
            return f"data: {data}\n\n"
        return f"data: {json.dumps(data)}\n\n"

    def start_message(self) -> str:
        """Start a new assistant message"""
        return ""

    def text_delta(self, content: str) -> str:
        """Stream a text chunk"""
        return self._sse({
            "type": "text-delta",
            "textDelta": content
        })

    def step_indicator(self, step_num: int) -> str:
        """Show step number as text (workaround since step events aren't supported)"""
        self.current_step = step_num
        # Don't emit anything - we'll include step in tool display
        return ""

    def tool_status(self, tool_name: str, status: str = "start", args: Optional[dict] = None,
                    tool_call_id: Optional[str] = None, result: Optional[Any] = None) -> str:
        """
        Stream tool status as formatted text.
        The Chat class doesn't support tool-call events, so we display as text.
        """
        if status == "start":
            # Show tool being called with step number and args
            step_prefix = f"**[{self.current_step}]** " if self.current_step > 0 else ""
            params = []
            if args:
                for k, v in args.items():
                    if isinstance(v, str):
                        display_v = v if len(v) < 50 else v[:47] + "..."
                        params.append(f"{k}={display_v}")
                    elif isinstance(v, list):
                        if len(v) <= 10:
                            params.append(f"{k}={v}")
                        else:
                            items = ', '.join(str(x) for x in v[:10])
                            params.append(f"{k}=[{items}... +{len(v)-10} more]")
                    elif isinstance(v, (int, float, bool)):
                        params.append(f"{k}={v}")
            param_str = f" ({', '.join(params)})" if params else ""
            text = f"{step_prefix}🔧 **{tool_name}**{param_str}\n"
        else:  # end
            text = f"✓ {tool_name} completado\n\n"

        return self.text_delta(text)

    def reasoning_text(self, content: str) -> str:
        """
        Stream reasoning/thinking as formatted text.
        The Chat class doesn't support reasoning events, so we display as collapsible text.
        """
        # Format as a blockquote for visual distinction
        return self.text_delta(f"> 💭 {content}\n")

    def error(self, message: str) -> str:
        """Stream an error"""
        return self._sse({
            "type": "error",
            "error": message
        })

    def finish(self, reason: str = "stop", usage: Optional[dict] = None) -> str:
        """Stream finish signal and close stream"""
        result = self._sse({
            "type": "finish",
            "finishReason": reason,
            "usage": usage or {}
        })
        # Send DONE marker to signal end of stream
        result += "data: [DONE]\n\n"
        return result


# Legacy adapter for backwards compatibility (old protocol format)
class LegacyStreamAdapter:
    """Old AI SDK Data Stream Protocol v1 format (0:, d:, etc.)"""

    @staticmethod
    def text(chunk: str) -> str:
        return f'0:{json.dumps(chunk)}\n'

    @staticmethod
    def data(payload: list) -> str:
        return f'2:{json.dumps(payload)}\n'

    @staticmethod
    def tool_call(tool_call_id: str, tool_name: str, args: dict) -> str:
        return f'9:{json.dumps({"toolCallId": tool_call_id, "toolName": tool_name, "args": args})}\n'

    @staticmethod
    def tool_result(tool_call_id: str, result: Any) -> str:
        return f'a:{json.dumps({"toolCallId": tool_call_id, "result": result})}\n'

    @staticmethod
    def error(message: str) -> str:
        return f'3:{json.dumps(message)}\n'

    @staticmethod
    def finish(reason: str = "stop", usage: Optional[dict] = None) -> str:
        payload = {"finishReason": reason}
        if usage:
            payload["usage"] = usage
        return f'd:{json.dumps(payload)}\n'
