"""
AI SDK Data Stream Protocol v1 Adapter.

Converts LangGraph events to AI SDK Data Stream Protocol format.
Documentation: https://sdk.vercel.ai/docs/ai-sdk-ui/stream-protocol

Stream Format Types:
- 0: text (chunk)
- 2: data (array of JSON values)
- 3: error (message)
- 9: tool_call (start)
- a: tool_result (end)
- d: finish (with reason and usage)
"""
import json
from typing import Any, List, Optional


class StreamAdapter:
    """Converts LangGraph events to AI SDK Data Stream Protocol v1"""

    @staticmethod
    def text(chunk: str) -> str:
        """Stream a text chunk (type 0)"""
        return f'0:{json.dumps(chunk)}\n'

    @staticmethod
    def data(payload: List[Any]) -> str:
        """Stream data as JSON array (type 2)"""
        return f'2:{json.dumps(payload)}\n'

    @staticmethod
    def tool_call(tool_call_id: str, tool_name: str, args: dict) -> str:
        """Stream tool call start (type 9)"""
        return f'9:{json.dumps({"toolCallId": tool_call_id, "toolName": tool_name, "args": args})}\n'

    @staticmethod
    def tool_result(tool_call_id: str, result: Any) -> str:
        """Stream tool result (type a)"""
        return f'a:{json.dumps({"toolCallId": tool_call_id, "result": result})}\n'

    @staticmethod
    def error(message: str) -> str:
        """Stream an error (type 3)"""
        return f'3:{json.dumps(message)}\n'

    @staticmethod
    def finish(reason: str = "stop", usage: Optional[dict] = None) -> str:
        """Stream finish signal (type d)"""
        payload = {"finishReason": reason}
        if usage:
            payload["usage"] = usage
        return f'd:{json.dumps(payload)}\n'
