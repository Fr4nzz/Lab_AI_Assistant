"""
Agent Conversation Logger

Logs the full AI conversation to a text file for evaluation/grading.
Includes: system prompt, context, user messages, AI responses, tool calls and results.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Log directory
LOG_DIR = Path(__file__).parent / "logs" / "agent_conversations"


class AgentConversationLogger:
    """
    Collects and saves the full AI conversation for evaluation.
    """

    def __init__(self, chat_id: str, model: str):
        self.chat_id = chat_id
        self.model = model
        self.start_time = datetime.now()
        self.entries: List[str] = []

        # Add header
        self.entries.append("=" * 80)
        self.entries.append(f"AGENT CONVERSATION LOG")
        self.entries.append(f"Chat ID: {chat_id}")
        self.entries.append(f"Model: {model}")
        self.entries.append(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.entries.append("=" * 80)
        self.entries.append("")

    def log_system_prompt(self, system_prompt: str):
        """Log the system prompt."""
        self.entries.append("-" * 40)
        self.entries.append("SYSTEM PROMPT:")
        self.entries.append("-" * 40)
        self.entries.append(system_prompt)
        self.entries.append("")

    def log_context(self, context: str, context_type: str = "CONTEXT"):
        """Log context information (orders, tabs, etc)."""
        self.entries.append("-" * 40)
        self.entries.append(f"{context_type}:")
        self.entries.append("-" * 40)
        self.entries.append(context)
        self.entries.append("")

    def log_user_message(self, message: Any, images_info: List[str] = None):
        """Log user message with image descriptions instead of base64."""
        self.entries.append("-" * 40)
        self.entries.append("USER MESSAGE:")
        self.entries.append("-" * 40)

        if isinstance(message, str):
            self.entries.append(message)
        elif isinstance(message, list):
            # Handle multimodal content
            for part in message:
                if isinstance(part, dict):
                    if part.get('type') == 'text':
                        self.entries.append(part.get('text', ''))
                    elif part.get('type') == 'image_url':
                        image_url = part.get('image_url', {})
                        url = image_url.get('url', '') if isinstance(image_url, dict) else str(image_url)
                        if url.startswith('data:'):
                            # Extract size info from base64
                            base64_parts = url.split(',', 1)
                            if len(base64_parts) > 1:
                                base64_size = len(base64_parts[1])
                                approx_bytes = int(base64_size * 0.75)
                                self.entries.append(f"[IMAGE: ~{approx_bytes // 1024}KB]")
                            else:
                                self.entries.append("[IMAGE]")
                        else:
                            self.entries.append(f"[IMAGE: {url[:100]}...]" if len(url) > 100 else f"[IMAGE: {url}]")
                    elif part.get('type') == 'media':
                        self.entries.append("[AUDIO/MEDIA]")
                elif isinstance(part, str):
                    self.entries.append(part)
        else:
            self.entries.append(str(message))

        if images_info:
            self.entries.append(f"Images: {', '.join(images_info)}")

        self.entries.append("")

    def log_tool_call(self, tool_name: str, tool_input: Dict[str, Any]):
        """Log AI tool call."""
        self.entries.append("-" * 40)
        self.entries.append(f"TOOL CALL: {tool_name}")
        self.entries.append("-" * 40)
        self.entries.append(f"Input: {json.dumps(tool_input, ensure_ascii=False, indent=2)}")
        self.entries.append("")

    def log_tool_result(self, tool_name: str, result: Any):
        """Log tool execution result."""
        self.entries.append("-" * 40)
        self.entries.append(f"TOOL RESULT: {tool_name}")
        self.entries.append("-" * 40)

        if isinstance(result, str):
            # Truncate very long results
            if len(result) > 5000:
                self.entries.append(result[:5000] + f"\n... [truncated, total {len(result)} chars]")
            else:
                self.entries.append(result)
        else:
            result_str = json.dumps(result, ensure_ascii=False, indent=2)
            if len(result_str) > 5000:
                self.entries.append(result_str[:5000] + f"\n... [truncated]")
            else:
                self.entries.append(result_str)

        self.entries.append("")

    def log_ai_response(self, response: str):
        """Log AI text response."""
        self.entries.append("-" * 40)
        self.entries.append("AI RESPONSE:")
        self.entries.append("-" * 40)
        self.entries.append(response)
        self.entries.append("")

    def log_thinking(self, thought: str):
        """Log AI thinking/reasoning."""
        self.entries.append("-" * 40)
        self.entries.append("AI THINKING:")
        self.entries.append("-" * 40)
        self.entries.append(thought)
        self.entries.append("")

    def log_error(self, error: str):
        """Log an error."""
        self.entries.append("-" * 40)
        self.entries.append("ERROR:")
        self.entries.append("-" * 40)
        self.entries.append(error)
        self.entries.append("")

    def save(self) -> str:
        """Save the log to a file and return the file path."""
        # Ensure log directory exists
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Add footer
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        self.entries.append("")
        self.entries.append("=" * 80)
        self.entries.append(f"END OF CONVERSATION")
        self.entries.append(f"Ended: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.entries.append(f"Duration: {duration:.2f}s")
        self.entries.append("=" * 80)

        # Generate filename
        timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{self.model}_{self.chat_id[:8]}.txt"
        filepath = LOG_DIR / filename

        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.entries))

        return str(filepath)
