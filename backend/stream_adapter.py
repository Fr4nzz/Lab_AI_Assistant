"""
AI SDK UI Message Stream Protocol v1 Adapter.

Converts LangGraph events to AI SDK v6 UI Message Stream Protocol format.
Documentation: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol

Stream Format (SSE):
- data: {"type":"start","messageId":"xxx"}
- data: {"type":"text-start","id":"xxx"}
- data: {"type":"text-delta","id":"xxx","delta":"content"}
- data: {"type":"text-end","id":"xxx"}
- data: {"type":"reasoning-start","id":"xxx"}
- data: {"type":"reasoning-delta","id":"xxx","delta":"content"}
- data: {"type":"reasoning-end","id":"xxx"}
- data: {"type":"tool-input-start","toolCallId":"xxx","toolName":"xxx"}
- data: {"type":"tool-input-available","toolCallId":"xxx","toolName":"xxx","input":{}}
- data: {"type":"tool-output-available","toolCallId":"xxx","output":{}}
- data: {"type":"start-step"}
- data: {"type":"finish-step"}
- data: {"type":"finish"}
- data: [DONE]
"""
import json
import uuid
from typing import Any, Optional


class StreamAdapter:
    """Converts LangGraph events to AI SDK v6 UI Message Stream Protocol"""

    def __init__(self):
        self.message_id = f"msg_{uuid.uuid4().hex}"
        self.text_id: Optional[str] = None
        self.reasoning_id: Optional[str] = None
        self.current_step = 0
        self.active_tool_calls: dict[str, str] = {}  # tool_call_id -> tool_name

    def _sse(self, data: Any) -> str:
        """Format data as SSE event"""
        if isinstance(data, str):
            return f"data: {data}\n\n"
        return f"data: {json.dumps(data)}\n\n"

    def start_message(self) -> str:
        """Start a new assistant message - REQUIRED for AI SDK to create message parts"""
        return self._sse({
            "type": "start",
            "messageId": self.message_id
        })

    def start_step(self) -> str:
        """Start a new step"""
        self.current_step += 1
        return self._sse({"type": "start-step"})

    def finish_step(self) -> str:
        """Finish current step"""
        result = ""
        # End any open text or reasoning blocks
        if self.text_id:
            result += self.text_end()
        if self.reasoning_id:
            result += self.reasoning_end()
        result += self._sse({"type": "finish-step"})
        return result

    def text_start(self) -> str:
        """Start a text block"""
        self.text_id = f"text_{uuid.uuid4().hex[:12]}"
        return self._sse({
            "type": "text-start",
            "id": self.text_id
        })

    def text_delta(self, content: str) -> str:
        """Stream a text chunk"""
        result = ""
        # Auto-start text block if not started
        if not self.text_id:
            result += self.text_start()
        result += self._sse({
            "type": "text-delta",
            "id": self.text_id,
            "delta": content
        })
        return result

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

    def reasoning_start(self) -> str:
        """Start a reasoning block"""
        self.reasoning_id = f"reasoning_{uuid.uuid4().hex[:12]}"
        return self._sse({
            "type": "reasoning-start",
            "id": self.reasoning_id
        })

    def reasoning_delta(self, content: str) -> str:
        """Stream reasoning/thinking content"""
        result = ""
        # Auto-start reasoning block if not started
        if not self.reasoning_id:
            result += self.reasoning_start()
        result += self._sse({
            "type": "reasoning-delta",
            "id": self.reasoning_id,
            "delta": content
        })
        return result

    def reasoning_end(self) -> str:
        """End a reasoning block"""
        if not self.reasoning_id:
            return ""
        result = self._sse({
            "type": "reasoning-end",
            "id": self.reasoning_id
        })
        self.reasoning_id = None
        return result

    def tool_start(self, tool_call_id: str, tool_name: str) -> str:
        """Start a tool call"""
        self.active_tool_calls[tool_call_id] = tool_name
        return self._sse({
            "type": "tool-input-start",
            "toolCallId": tool_call_id,
            "toolName": tool_name
        })

    def tool_input_available(self, tool_call_id: str, tool_name: str, args: dict) -> str:
        """Signal tool input is available"""
        return self._sse({
            "type": "tool-input-available",
            "toolCallId": tool_call_id,
            "toolName": tool_name,
            "input": args
        })

    def tool_output_available(self, tool_call_id: str, output: Any) -> str:
        """Signal tool output is available"""
        # Convert output to appropriate format
        if isinstance(output, (dict, list)):
            output_data = output
        else:
            output_data = str(output) if output else "completed"

        return self._sse({
            "type": "tool-output-available",
            "toolCallId": tool_call_id,
            "output": output_data
        })

    def tool_status(self, tool_name: str, status: str = "start", args: Optional[dict] = None,
                    tool_call_id: Optional[str] = None, result: Optional[Any] = None) -> str:
        """Stream tool status using AI SDK protocol"""
        import logging
        logger = logging.getLogger(__name__)

        if status == "start":
            # Generate tool call ID if not provided
            if not tool_call_id:
                tool_call_id = f"call_{uuid.uuid4().hex[:12]}"

            # Store for later lookup
            self.active_tool_calls[tool_call_id] = tool_name

            # Emit tool-input-start followed by tool-input-available
            output = self.tool_start(tool_call_id, tool_name)
            output += self.tool_input_available(tool_call_id, tool_name, args or {})
            logger.info(f"[StreamAdapter] Tool start: {tool_name} ({tool_call_id})")
            return output
        else:  # end
            # Find the tool call ID
            actual_id = tool_call_id
            if not actual_id:
                # Try to find by tool name
                for tid, tname in list(self.active_tool_calls.items()):
                    if tname == tool_name:
                        actual_id = tid
                        break

            output = ""
            if actual_id:
                # Emit tool-output-available
                output = self.tool_output_available(actual_id, result)
                logger.info(f"[StreamAdapter] Tool end: {tool_name} ({actual_id})")
                # Remove from active calls
                self.active_tool_calls.pop(actual_id, None)
            else:
                logger.warning(f"[StreamAdapter] Tool end but no matching ID for: {tool_name}")

            return output

    def error(self, message: str) -> str:
        """Stream an error"""
        return self._sse({
            "type": "error",
            "errorText": message
        })

    def finish(self, reason: str = "stop", usage: Optional[dict] = None) -> str:
        """Stream finish signal and close stream"""
        result = ""
        # End any open blocks
        if self.text_id:
            result += self.text_end()
        if self.reasoning_id:
            result += self.reasoning_end()
        # Send finish event
        result += self._sse({"type": "finish"})
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
