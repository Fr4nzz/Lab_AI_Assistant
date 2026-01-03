"""
MCP Tools Wrapper for Claude Agent SDK.

Creates MCP tools that wrap the existing LangGraph tool implementations.
This allows Claude to use the same tools as Gemini (search_orders, edit_results, etc.)
without duplicating business logic.

Note: We use manual MCP tool wrappers instead of langchain-tool-to-mcp-adapter
because the adapter has dependency conflicts with our LangChain version.
"""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Track initialization status
_mcp_server = None
_mcp_tools_available = False


def get_mcp_tool_names() -> List[str]:
    """
    Get the list of MCP tool names in the format Claude expects.

    Tool naming convention: mcp__[server_name]__[tool_name]
    """
    return [
        "mcp__lab__search_orders",
        "mcp__lab__get_order_results",
        "mcp__lab__get_order_info",
        "mcp__lab__edit_results",
        "mcp__lab__edit_order_exams",
        "mcp__lab__create_new_order",
        "mcp__lab__ask_user",
        "mcp__lab__get_available_exams",
    ]


def create_lab_mcp_server():
    """
    Create an MCP server with all lab tools.

    Uses manual MCP tool wrappers that call the existing LangGraph implementations.

    Returns:
        MCP server instance or None if creation fails
    """
    global _mcp_server, _mcp_tools_available

    if _mcp_server is not None:
        return _mcp_server

    return _create_manual_mcp_server()


def _create_manual_mcp_server():
    """
    Create MCP tools using claude-agent-sdk's @tool decorator.

    Wraps the existing LangGraph tool implementations directly.
    """
    global _mcp_server, _mcp_tools_available

    try:
        from claude_agent_sdk import tool as mcp_tool, create_sdk_mcp_server
        from graph.tools import (
            _search_orders_impl,
            _get_order_results_impl,
            _get_order_info_impl,
            _edit_results_impl,
            _edit_order_exams_impl,
            _create_order_impl,
            _get_available_exams_impl,
        )
        import json

        # Define MCP tools wrapping the existing implementations

        @mcp_tool(
            "search_orders",
            "Search orders by patient name. Returns 'num' and 'id' for each order.",
            {
                "search": str,
                "limit": int,
                "page_num": int,
                "fecha_desde": str,
                "fecha_hasta": str,
            }
        )
        async def search_orders(args):
            result = await _search_orders_impl(
                search=args.get("search", ""),
                limit=args.get("limit", 20),
                page_num=args.get("page_num", 1),
                fecha_desde=args.get("fecha_desde"),
                fecha_hasta=args.get("fecha_hasta"),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "get_order_results",
            "Get result fields for orders. BATCH: pass ALL order_nums at once.",
            {"order_nums": list}
        )
        async def get_order_results(args):
            result = await _get_order_results_impl(args.get("order_nums", []))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "get_order_info",
            "Get order details and exams list. BATCH: pass ALL order_ids at once.",
            {"order_ids": list}
        )
        async def get_order_info(args):
            result = await _get_order_info_impl(args.get("order_ids", []))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "edit_results",
            "Edit result fields. BATCH all: data=[{orden, e (exam), f (field), v (value)}]",
            {"data": list}
        )
        async def edit_results(args):
            result = await _edit_results_impl(args.get("data", []))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "edit_order_exams",
            "Edit order: add/remove exams, set cedula. Use order_id for saved orders, tab_index for new orders.",
            {
                "order_id": int,
                "tab_index": int,
                "add": list,
                "remove": list,
                "cedula": str,
            }
        )
        async def edit_order_exams(args):
            result = await _edit_order_exams_impl(
                order_id=args.get("order_id"),
                tab_index=args.get("tab_index"),
                add=args.get("add"),
                remove=args.get("remove"),
                cedula=args.get("cedula"),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "create_new_order",
            'Create order. cedula="" for cotización. exams=["BH","EMO"]',
            {"cedula": str, "exams": list}
        )
        async def create_new_order(args):
            result = await _create_order_impl(
                cedula=args.get("cedula", ""),
                exams=args.get("exams", []),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "ask_user",
            "Display message with clickable options to the user. After calling, stop and wait for user input.",
            {"message": str, "options": list}
        )
        async def ask_user(args):
            result = {
                "message": args.get("message", ""),
                "status": "waiting_for_user"
            }
            if args.get("options"):
                result["options"] = args["options"]
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "get_available_exams",
            "Get available exam codes. If order_id given, also returns added exams.",
            {"order_id": int}
        )
        async def get_available_exams(args):
            result = await _get_available_exams_impl(order_id=args.get("order_id"))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        # Create the MCP server
        server = create_sdk_mcp_server(
            name="lab",
            version="1.0.0",
            tools=[
                search_orders,
                get_order_results,
                get_order_info,
                edit_results,
                edit_order_exams,
                create_new_order,
                ask_user,
                get_available_exams,
            ]
        )

        _mcp_server = server
        _mcp_tools_available = True
        logger.info("[MCP] Lab MCP server created manually with 8 tools")
        return server

    except Exception as e:
        logger.error(f"[MCP] Failed to create manual MCP server: {e}")
        _mcp_tools_available = False
        return None


def is_mcp_available() -> bool:
    """Check if MCP tools are available."""
    global _mcp_tools_available
    if _mcp_server is None:
        # Try to create the server
        create_lab_mcp_server()
    return _mcp_tools_available


def get_mcp_server():
    """Get the MCP server, creating it if necessary."""
    global _mcp_server
    if _mcp_server is None:
        create_lab_mcp_server()
    return _mcp_server
