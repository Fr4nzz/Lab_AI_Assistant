"""
LangGraph State Schema for Lab Assistant.

DOCUMENTATION:
- State Schema: https://langchain-ai.github.io/langgraph/concepts/low_level/#state
- Reducers (add_messages): https://langchain-ai.github.io/langgraph/concepts/low_level/#reducers
- TypedDict: Standard Python typing

KEY CONCEPTS:
- Annotated[list, add_messages] - Messages are APPENDED, not replaced
- Other fields are REPLACED by default
- State persists across conversation via checkpointer

NOTE: No approval/interrupt fields needed - the website's Save button
is the human-in-the-loop mechanism. AI can freely fill forms.
"""
from typing import Annotated, Optional, List, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class LabAssistantState(TypedDict):
    """
    Complete state for the Lab Assistant agent.

    Attributes:
        messages: Conversation history (uses add_messages reducer - appends)
        current_page_context: Extracted data from current browser page
        current_page_type: Type of page ("ordenes_list", "reportes", etc.)
        active_tabs: Dict of open browser tabs {orden_num: tab_info}
        execution_results: Results from tool executions in current turn
    """
    # Core conversation (REDUCER: appends new messages)
    messages: Annotated[List[BaseMessage], add_messages]

    # Browser/page context (updated by navigation tools)
    current_page_context: Optional[Dict[str, Any]]
    current_page_type: Optional[str]  # "ordenes_list", "reportes", "orden_edit", etc.

    # Tab management for batch editing
    active_tabs: Optional[Dict[str, Dict[str, Any]]]  # {orden_num: {page, data}}

    # Tool execution tracking for current turn
    execution_results: Optional[List[Dict[str, Any]]]
