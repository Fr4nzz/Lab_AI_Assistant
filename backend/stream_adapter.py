"""
AI SDK UI Message Stream Protocol v1 Adapter.

Converts LangGraph events to AI SDK v6 UI Message Stream Protocol format.
Documentation: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol

Stream Format (SSE):
- data: {"type":"start","messageId":"xxx"}
- data: {"type":"text-start","id":"xxx"}
- data: {"type":"text-delta","id":"xxx","delta":"content"}
- data: {"type":"text-end","id":"xxx"}
- data: {"type":"tool-input-start","id":"xxx","toolName":"xxx"}
- data: {"type":"tool-input-available","id":"xxx","input":{}}
- data: {"type":"tool-output-available","id":"xxx","output":"xxx"}
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
        self.text_id = None
        self.message_started = False

    def _sse(self, data: Any) -> str:
        """Format data as SSE event"""
        if isinstance(data, str):
            return f"data: {data}\n\n"
        return f"data: {json.dumps(data)}\n\n"

    def start_message(self) -> str:
        """Start a new assistant message"""
        self.message_started = True
        return self._sse({
            "type": "start",
            "messageId": self.message_id
        })

    def text_start(self) -> str:
        """Start a text block"""
        self.text_id = f"text_{uuid.uuid4().hex[:8]}"
        return self._sse({
            "type": "text-start",
            "id": self.text_id
        })

    def text_delta(self, content: str) -> str:
        """Stream a text chunk"""
        if not self.text_id:
            # Auto-start text block if not started
            result = self.text_start()
            result += self._sse({
                "type": "text-delta",
                "id": self.text_id,
                "delta": content
            })
            return result
        return self._sse({
            "type": "text-delta",
            "id": self.text_id,
            "delta": content
        })

    def text_end(self) -> str:
        """End a text block"""
        if not self.text_id:
            return ""
        result = self._sse({
            "type": "text-end",
            "id": self.text_id
        })
        self.text_id = None
        return result

    def tool_start(self, tool_call_id: str, tool_name: str) -> str:
        """Stream tool call start"""
        return self._sse({
            "type": "tool-input-start",
            "id": tool_call_id,
            "toolName": tool_name
        })

    def tool_input(self, tool_call_id: str, args: dict) -> str:
        """Stream tool input available"""
        return self._sse({
            "type": "tool-input-available",
            "id": tool_call_id,
            "input": args
        })

    def tool_output(self, tool_call_id: str, output: Any) -> str:
        """Stream tool output"""
        return self._sse({
            "type": "tool-output-available",
            "id": tool_call_id,
            "output": str(output)[:500] if output else ""
        })

    def error(self, message: str) -> str:
        """Stream an error"""
        return self._sse({
            "type": "error",
            "error": message
        })

    def finish(self, reason: str = "stop", usage: Optional[dict] = None) -> str:
        """Stream finish signal and close stream"""
        result = ""
        # End any open text block
        if self.text_id:
            result += self.text_end()

        # Send finish
        payload = {
            "type": "finish",
            "finishReason": reason
        }
        if usage:
            payload["usage"] = usage
        result += self._sse(payload)

        # Send DONE marker
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
