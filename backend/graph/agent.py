"""
LangGraph Agent for Lab Assistant.

DOCUMENTATION:
- StateGraph: https://langchain-ai.github.io/langgraph/concepts/low_level/#stategraph
- Nodes and Edges: https://langchain-ai.github.io/langgraph/concepts/low_level/#nodes
- Conditional Edges: https://langchain-ai.github.io/langgraph/concepts/low_level/#conditional-edges
- Prebuilt ReAct: https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/

ARCHITECTURE (Simple - No Approval Needed):
+---------+     +---------+     +---------+
|  START  |---->|  Agent  |---->|  Tools  |
+---------+     +----+----+     +----+----+
                     |               |
                     |<--------------+
                     |
                     v (no tool calls)
               +---------+
               |   END   |
               +---------+

All tools are SAFE - they only fill browser forms.
The website's "Guardar" button is the human-in-the-loop.

OPTIMIZATION GOAL:
- Current system: 5 iterations (search -> get_fields -> edit -> ask_user -> summary)
- Target: 3 iterations (search -> get_fields -> edit+respond)
- Key: Agent should respond directly after edit_results, no need for ask_user
"""
from typing import Literal
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .state import LabAssistantState
from .tools import ALL_TOOLS, set_browser
from models import get_chat_model
from prompts import SYSTEM_PROMPT


def create_lab_agent(browser_manager=None):
    """
    Create the LangGraph agent for lab assistance.

    This is a simple ReAct-style agent:
    1. Agent receives message, decides on tool calls
    2. Tools execute (browser automation)
    3. Agent sees results, decides next action or responds
    4. Loop until agent responds without tool calls

    Args:
        browser_manager: BrowserManager instance for Playwright control

    Returns:
        StateGraph builder (compile with checkpointer before use)
    """
    if browser_manager:
        set_browser(browser_manager)

    # Get model and bind tools
    model = get_chat_model()
    model_with_tools = model.bind_tools(ALL_TOOLS)

    # ============================================================
    # NODE DEFINITIONS
    # ============================================================

    def agent_node(state: LabAssistantState) -> dict:
        """
        Main agent node - calls LLM with conversation history.

        The LLM decides whether to:
        1. Call tools to gather info or take action
        2. Respond directly to the user (ends the loop)
        """
        # Build system message with current context
        context_str = ""
        page_context = state.get("current_page_context")
        if page_context:
            # Handle both string and dict context
            if isinstance(page_context, str):
                context_str = f"\n\nCONTEXTO ACTUAL (Órdenes en pantalla):\n{page_context}"
            else:
                import json
                context_str = f"\n\nCONTEXTO ACTUAL:\n{json.dumps(page_context, ensure_ascii=False)}"

        # Use simplified prompt for LangGraph (tools are already bound)
        system_content = SYSTEM_PROMPT + context_str
        system_msg = SystemMessage(content=system_content)

        # Build message list
        messages = [system_msg] + list(state["messages"])

        # Log for debugging
        logger.info(f"[Agent] Invoking LLM with {len(messages)} messages, context: {len(context_str)} chars")

        # Call LLM
        response = model_with_tools.invoke(messages)

        # Detailed logging of response
        logger.debug(f"[Agent] Raw response type: {type(response)}")
        logger.debug(f"[Agent] Response attributes: {[a for a in dir(response) if not a.startswith('_')]}")

        if hasattr(response, 'tool_calls') and response.tool_calls:
            logger.info(f"[Agent] LLM returned {len(response.tool_calls)} tool calls:")
            for tc in response.tool_calls:
                logger.info(f"  -> {tc.get('name', 'unknown')}")
        elif response.content:
            content_preview = response.content[:200] if len(response.content) > 200 else response.content
            logger.info(f"[Agent] LLM response: {content_preview}")
        else:
            logger.warning(f"[Agent] LLM returned empty response! Raw: {response}")

        return {"messages": [response]}

    # ============================================================
    # ROUTING FUNCTION
    # ============================================================

    def should_continue(state: LabAssistantState) -> Literal["tools", "__end__"]:
        """
        Determine if we should execute tools or end.

        Simple logic:
        - If last message has tool_calls -> execute them
        - Otherwise -> end (agent has responded to user)
        """
        last_message = state["messages"][-1]

        # Check if there are tool calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        # No tool calls - agent is done, return response to user
        return END

    # ============================================================
    # GRAPH CONSTRUCTION
    # ============================================================

    builder = StateGraph(LabAssistantState)

    # Add nodes
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(ALL_TOOLS))

    # Add edges
    builder.add_edge(START, "agent")

    # Conditional edge from agent
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )

    # After tools, always go back to agent
    builder.add_edge("tools", "agent")

    return builder


def compile_agent(builder: StateGraph, checkpointer=None):
    """
    Compile the agent graph, optionally with a checkpointer.

    DOCUMENTATION:
    - Checkpointers: https://langchain-ai.github.io/langgraph/concepts/persistence/
    - MemorySaver: For development/testing (in-memory)
    - SqliteSaver: For production with SQLite
    - PostgresSaver: For production with PostgreSQL

    Checkpointer enables:
    - Conversation persistence across requests
    - State recovery after crashes
    - Thread-based conversation isolation

    Args:
        builder: Configured StateGraph builder
        checkpointer: Optional checkpointer for persistence

    Returns:
        Compiled graph ready for invocation
    """
    if checkpointer:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()


# ============================================================
# ALTERNATIVE: Use Prebuilt ReAct Agent
# ============================================================

def create_react_agent_simple(browser_manager=None):
    """
    Alternative: Use LangGraph's prebuilt create_react_agent.

    This is simpler but less customizable.

    DOCUMENTATION:
    https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/
    """
    from langgraph.prebuilt import create_react_agent

    if browser_manager:
        set_browser(browser_manager)

    model = get_chat_model()

    return create_react_agent(
        model=model,
        tools=ALL_TOOLS,
        state_schema=LabAssistantState
    )
