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
import json
import re
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# Directory for LLM call logs
LLM_LOG_DIR = Path(__file__).parent.parent / "data" / "llm_calls"


def summarize_content_for_log(content):
    """Summarize content for logging, truncating base64 data."""
    if isinstance(content, str):
        # Truncate long base64 data URLs
        if content.startswith('data:') and len(content) > 200:
            mime_match = re.match(r'^data:([^;]+)', content)
            return f"[DATA URL: {mime_match.group(1) if mime_match else 'unknown'}, {len(content)} chars]"
        return content
    if isinstance(content, list):
        result = []
        for item in content:
            if isinstance(item, dict):
                summarized = {}
                for k, v in item.items():
                    if k in ('data', 'url', 'image_url') and isinstance(v, str) and len(v) > 200:
                        if isinstance(v, str) and v.startswith('data:'):
                            mime_match = re.match(r'^data:([^;]+)', v)
                            summarized[k] = f"[DATA URL: {mime_match.group(1) if mime_match else 'unknown'}, {len(v)} chars]"
                        else:
                            summarized[k] = f"[BASE64: {len(v)} chars]"
                    elif isinstance(v, dict) and 'url' in v:
                        # Handle nested image_url: {url: "data:..."}
                        url = v.get('url', '')
                        if isinstance(url, str) and len(url) > 200:
                            summarized[k] = {"url": f"[DATA URL: {len(url)} chars]"}
                        else:
                            summarized[k] = v
                    else:
                        summarized[k] = v
                result.append(summarized)
            else:
                result.append(item)
        return result
    return content


def log_llm_call(call_num: int, messages: list, response, tools_bound: bool = False):
    """
    Log the full LLM call to a JSON file for debugging.

    This shows EXACTLY what Gemini receives and returns.
    """
    LLM_LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"llm_{timestamp}_{call_num:02d}.json"

    # Serialize messages
    serialized_messages = []
    for msg in messages:
        msg_type = type(msg).__name__
        content = msg.content if hasattr(msg, 'content') else str(msg)

        # Summarize content to avoid huge files
        summarized_content = summarize_content_for_log(content)

        serialized_messages.append({
            "type": msg_type,
            "content": summarized_content,
            "content_length": len(str(content)),
        })

    # Serialize response
    response_data = {
        "type": type(response).__name__,
        "content": summarize_content_for_log(response.content) if hasattr(response, 'content') else str(response),
        "content_length": len(str(response.content)) if hasattr(response, 'content') else 0,
    }

    if hasattr(response, 'tool_calls') and response.tool_calls:
        response_data["tool_calls"] = [
            {"name": tc.get('name'), "args": tc.get('args')}
            for tc in response.tool_calls
        ]

    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        response_data["usage"] = dict(response.usage_metadata)

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "call_number": call_num,
        "tools_bound": tools_bound,
        "input_messages": serialized_messages,
        "input_total_chars": sum(m["content_length"] for m in serialized_messages),
        "response": response_data,
    }

    filepath = LLM_LOG_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    logger.info(f"[LLM] Logged call #{call_num} to {filename} (input: {log_data['input_total_chars']} chars)")

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

    # Track LLM call count for logging
    llm_call_counter = [0]  # Use list to allow mutation in nested function

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

        # Call LLM with retry on empty response
        max_empty_retries = 2
        for attempt in range(max_empty_retries + 1):
            response = model_with_tools.invoke(messages)

            # Check if response is empty (no content and no tool calls)
            has_content = bool(response.content)
            has_tool_calls = hasattr(response, 'tool_calls') and bool(response.tool_calls)

            if has_content or has_tool_calls:
                break  # Got a valid response

            if attempt < max_empty_retries:
                logger.warning(f"[Agent] Empty response, retrying ({attempt + 1}/{max_empty_retries})...")
                import time
                time.sleep(2)  # Brief wait before retry
            else:
                logger.error(f"[Agent] LLM returned empty after {max_empty_retries + 1} attempts")

        # Log the full LLM call for debugging
        llm_call_counter[0] += 1
        log_llm_call(llm_call_counter[0], messages, response, tools_bound=True)

        # Log thinking if present (Gemini 3+ with include_thoughts=True)
        if hasattr(response, 'additional_kwargs'):
            thoughts = response.additional_kwargs.get('thoughts', [])
            if thoughts:
                for thought in thoughts[:2]:  # Show first 2 thoughts
                    thought_preview = thought[:300] + "..." if len(thought) > 300 else thought
                    logger.info(f"[Agent] 💭 Thinking: {thought_preview}")

        # Log response type
        if hasattr(response, 'tool_calls') and response.tool_calls:
            logger.info(f"[Agent] LLM returned {len(response.tool_calls)} tool calls:")
            for tc in response.tool_calls:
                logger.info(f"  -> {tc.get('name', 'unknown')}")
        elif response.content:
            # Handle both string and list content (Gemini 3 with thinking)
            content = response.content
            if isinstance(content, list):
                # Extract text parts only for logging
                text_parts = [p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'text']
                content = ''.join(text_parts)
            content_preview = content[:200] if len(content) > 200 else content
            logger.info(f"[Agent] LLM response: {content_preview}")
        else:
            logger.warning(f"[Agent] LLM returned empty! response: {response}")

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
