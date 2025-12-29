"""
AI SDK UI Message Stream Protocol v1 Adapter.

Converts LangGraph events to AI SDK v6 UI Message Stream Protocol format.
Documentation: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol

Stream Format (SSE):
- data: {"type":"text-delta","textDelta":"content"}
- data: {"type":"tool-call","toolCallId":"xxx","toolName":"xxx","args":{}}
- data: {"type":"tool-result","toolCallId":"xxx","result":"xxx"}
- data: {"type":"reasoning","textDelta":"thinking..."}
- data: {"type":"step-start"}
- data: {"type":"step-finish"}
- data: {"type":"finish","finishReason":"stop","usage":{}}
- data: [DONE]
"""
import json
import uuid
from typing import Any, Optional


class StreamAdapter:
    """Converts LangGraph events to AI SDK v6 UI Message Stream Protocol"""

    def __init__(self):
        self.message_id = f"msg_{uuid.uuid4().hex[:12]}"
        self.text_started = False
        self.current_step = 0
        self.active_tool_calls: dict[str, str] = {}  # tool_call_id -> tool_name

    def _sse(self, data: Any) -> str:
        """Format data as SSE event"""
        if isinstance(data, str):
            return f"data: {data}\n\n"
        return f"data: {json.dumps(data)}\n\n"

    def start_message(self) -> str:
        """Start a new assistant message"""
        return ""

    def step_start(self) -> str:
        """Start a new step (reasoning + actions)"""
        self.current_step += 1
        return self._sse({"type": "step-start"})

    def step_finish(self) -> str:
        """Finish current step"""
        return self._sse({"type": "step-finish"})

    def text_delta(self, content: str) -> str:
        """Stream a text chunk"""
        self.text_started = True
        return self._sse({
            "type": "text-delta",
            "textDelta": content
        })

    def reasoning_delta(self, content: str) -> str:
        """Stream reasoning/thinking content"""
        return self._sse({
            "type": "reasoning",
            "textDelta": content
        })

    def tool_call(self, tool_call_id: str, tool_name: str, args: dict) -> str:
        """Emit a tool call event"""
        self.active_tool_calls[tool_call_id] = tool_name
        return self._sse({
            "type": "tool-call",
            "toolCallId": tool_call_id,
            "toolName": tool_name,
            "args": args
        })

    def tool_result(self, tool_call_id: str, result: Any) -> str:
        """Emit a tool result event"""
        # Convert result to string if needed
        if isinstance(result, (dict, list)):
            result_str = json.dumps(result, ensure_ascii=False)
        else:
            result_str = str(result)

        # Remove from active calls
        self.active_tool_calls.pop(tool_call_id, None)

        return self._sse({
            "type": "tool-result",
            "toolCallId": tool_call_id,
            "result": result_str
        })

    def tool_status(self, tool_name: str, status: str = "start", args: Optional[dict] = None,
                    tool_call_id: Optional[str] = None, result: Optional[Any] = None) -> str:
        """
        Stream tool events using proper AI SDK format.
        Falls back to text display if tool events aren't supported.
        """
        if status == "start":
            # Generate tool call ID if not provided
            if not tool_call_id:
                tool_call_id = f"call_{uuid.uuid4().hex[:12]}"

            return self.tool_call(tool_call_id, tool_name, args or {})
        else:  # end
            # Find the tool call ID for this tool
            matching_id = None
            for tid, tname in list(self.active_tool_calls.items()):
                if tname == tool_name:
                    matching_id = tid
                    break

            if matching_id:
                return self.tool_result(matching_id, result or "completed")

            # Fallback to text if no matching call
            return self.text_delta(f"✓ {tool_name} completado\n\n")

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
