"""
MCP Tools Wrapper for Claude Agent SDK.

Creates MCP tools using claude-agent-sdk's create_sdk_mcp_server() for use with Claude Code.
This wraps the existing LangGraph tool implementations so Claude can use the same tools as Gemini.

IMPORTANT: Claude Agent SDK requires servers created with create_sdk_mcp_server(),
NOT FastMCP objects. FastMCP is for external servers, not in-process SDK use.

Reference: https://platform.claude.com/docs/en/agent-sdk/custom-tools
"""
import logging
import json
from typing import List, Optional, Dict, Any

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
    Create an MCP server with all lab tools for Claude Agent SDK.

    Uses claude-agent-sdk's create_sdk_mcp_server() which creates an in-process
    MCP server that can be passed directly to ClaudeAgentOptions.

    Returns:
        SDK MCP server instance or None if creation fails
    """
    global _mcp_server, _mcp_tools_available

    if _mcp_server is not None:
        return _mcp_server

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

        logger.info("[MCP] Creating lab MCP server with claude-agent-sdk...")

        # Define MCP tools wrapping the existing LangGraph implementations
        # Each tool returns {"content": [{"type": "text", "text": "..."}]} format

        @mcp_tool(
            "search_orders",
            "Search orders by patient name. Returns 'num' and 'id' for each order. Uses fuzzy search fallback if no exact matches.",
            {
                "search": str,
                "limit": int,
                "page_num": int,
                "fecha_desde": str,
                "fecha_hasta": str,
            }
        )
        async def search_orders(args: Dict[str, Any]) -> Dict[str, Any]:
            logger.debug(f"[MCP Tool] search_orders called with: {args}")
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
            "Get result fields for orders. BATCH: pass ALL order_nums at once. Opens reportes2 tabs.",
            {"order_nums": list}
        )
        async def get_order_results(args: Dict[str, Any]) -> Dict[str, Any]:
            logger.debug(f"[MCP Tool] get_order_results called with: {args}")
            result = await _get_order_results_impl(args.get("order_nums", []))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "get_order_info",
            "Get order details and exams list. BATCH: pass ALL order_ids at once.",
            {"order_ids": list}
        )
        async def get_order_info(args: Dict[str, Any]) -> Dict[str, Any]:
            logger.debug(f"[MCP Tool] get_order_info called with: {args}")
            result = await _get_order_info_impl(args.get("order_ids", []))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "edit_results",
            "Edit result fields. BATCH all edits: data=[{orden, e (exam name), f (field name), v (value)}]",
            {"data": list}
        )
        async def edit_results(args: Dict[str, Any]) -> Dict[str, Any]:
            logger.debug(f"[MCP Tool] edit_results called with: {args}")
            result = await _edit_results_impl(args.get("data", []))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "edit_order_exams",
            "Edit order: add/remove exams, set cedula. Use order_id for saved orders, tab_index for new orders from CONTEXT.",
            {
                "order_id": int,
                "tab_index": int,
                "add": list,
                "remove": list,
                "cedula": str,
            }
        )
        async def edit_order_exams(args: Dict[str, Any]) -> Dict[str, Any]:
            logger.debug(f"[MCP Tool] edit_order_exams called with: {args}")
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
            'Create new order. cedula="" for cotización (quote without patient). exams=["BH","EMO",...]',
            {"cedula": str, "exams": list}
        )
        async def create_new_order(args: Dict[str, Any]) -> Dict[str, Any]:
            logger.debug(f"[MCP Tool] create_new_order called with: {args}")
            result = await _create_order_impl(
                cedula=args.get("cedula", ""),
                exams=args.get("exams", []),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "ask_user",
            "Display message with clickable options to the user. After calling this, STOP and wait for user input.",
            {"message": str, "options": list}
        )
        async def ask_user(args: Dict[str, Any]) -> Dict[str, Any]:
            logger.debug(f"[MCP Tool] ask_user called with: {args}")
            result = {
                "message": args.get("message", ""),
                "status": "waiting_for_user"
            }
            if args.get("options"):
                result["options"] = args["options"]
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @mcp_tool(
            "get_available_exams",
            "Get list of available exam codes with prices. If order_id given, also returns exams already added to that order.",
            {"order_id": int}
        )
        async def get_available_exams(args: Dict[str, Any]) -> Dict[str, Any]:
            logger.debug(f"[MCP Tool] get_available_exams called with: {args}")
            result = await _get_available_exams_impl(order_id=args.get("order_id"))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        # Create the SDK MCP server (this is what ClaudeAgentOptions expects)
        tools_list = [
            search_orders,
            get_order_results,
            get_order_info,
            edit_results,
            edit_order_exams,
            create_new_order,
            ask_user,
            get_available_exams,
        ]

        server = create_sdk_mcp_server(
            name="lab",
            version="1.0.0",
            tools=tools_list
        )

        _mcp_server = server
        _mcp_tools_available = True

        # Log tool definitions for debugging
        tool_names = [t.__name__ for t in tools_list]
        logger.info(f"[MCP] Lab MCP server created with {len(tools_list)} tools: {tool_names}")

        return server

    except ImportError as e:
        logger.error(f"[MCP] claude-agent-sdk not available: {e}")
        _mcp_tools_available = False
        return None
    except Exception as e:
        logger.error(f"[MCP] Failed to create MCP server: {e}", exc_info=True)
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
