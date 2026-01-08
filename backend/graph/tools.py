"""
LangChain-compatible tool definitions for Lab Assistant.

DOCUMENTATION:
- @tool decorator: https://python.langchain.com/docs/how_to/custom_tools/
- Async tools: Tools can be async - LangGraph handles them properly

DESIGN PRINCIPLES:
1. ALL tools are safe - they only fill forms, never save
2. Batch operations - accept arrays to minimize iterations
3. Return strings (will be added to messages)
4. The website's Save button is the human-in-the-loop mechanism
5. Tools find existing tabs by ID or create new ones if not found
"""
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field
import json
import sys
import logging
import re
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from browser_manager import BrowserManager
from extractors import (
    EXTRACT_ORDENES_JS, EXTRACT_REPORTES_JS, EXTRACT_ORDEN_EDIT_JS,
    EXTRACT_AVAILABLE_EXAMS_JS, EXTRACT_ADDED_EXAMS_JS, PageDataExtractor
)
from orders_cache import fuzzy_search_patient, format_fuzzy_results

logger = logging.getLogger(__name__)

# Global browser instance (will be set during app startup)
_browser: Optional[BrowserManager] = None

# Tab tracking by ID
# Key: order_num (str) for reportes2 tabs, order_id (int) for ordenes/edit tabs
_results_tabs: Dict[str, Any] = {}  # {order_num: Page} - for reportes2
_order_tabs: Dict[int, Any] = {}     # {order_id: Page} - for ordenes/edit


class TabStateManager:
    """
    Manages tab state tracking to send only changed info to AI.

    - Tracks known state per tab (what AI has seen)
    - Computes delta between known and current state
    - Enumerates duplicate tabs with same order/report
    """

    def __init__(self):
        # Known state per tab, keyed by unique tab identifier
        # Format: {tab_key: {state_dict}}
        self._known_states: Dict[str, Dict] = {}
        # Track which tabs AI knows about
        self._known_tab_keys: set = set()

    def _get_tab_key(self, url: str, index: int) -> str:
        """Generate unique key for a tab based on URL and index."""
        return f"{index}:{url}"

    def compute_state_delta(self, known: Dict, current: Dict) -> Dict:
        """Compute what changed between known and current state."""
        if not known:
            return current  # All is new

        delta = {}
        for key, value in current.items():
            if key not in known:
                delta[key] = value
            elif known[key] != value:
                # For nested dicts/lists, just mark as changed
                delta[key] = value

        return delta

    def update_known_state(self, tab_key: str, state: Dict):
        """Update known state for a tab after AI has seen it."""
        self._known_states[tab_key] = state.copy() if state else {}
        self._known_tab_keys.add(tab_key)

    def get_known_state(self, tab_key: str) -> Optional[Dict]:
        """Get known state for a tab."""
        return self._known_states.get(tab_key)

    def is_new_tab(self, tab_key: str) -> bool:
        """Check if this is a new tab AI hasn't seen."""
        return tab_key not in self._known_tab_keys

    def clear_closed_tabs(self, current_tab_keys: set):
        """Remove state for tabs that are no longer open."""
        closed = self._known_tab_keys - current_tab_keys
        for key in closed:
            self._known_states.pop(key, None)
        self._known_tab_keys = self._known_tab_keys & current_tab_keys

    def reset(self):
        """Reset all known states (e.g., on new conversation)."""
        self._known_states.clear()
        self._known_tab_keys.clear()


# Global tab state manager
_tab_state_manager = TabStateManager()


# CSS for highlighting modified fields
HIGHLIGHT_STYLES = """
    .ai-modified {
        background-color: #fef3c7 !important;
        border: 2px solid #f59e0b !important;
        box-shadow: 0 0 8px rgba(245, 158, 11, 0.4) !important;
    }
    .ai-modified-row {
        background-color: #fffbeb !important;
    }
    .ai-change-badge {
        display: inline-block;
        background: #dc2626;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 11px;
        margin-left: 8px;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
"""

# JavaScript for filling a field and auto-highlighting
FILL_FIELD_JS = r"""
(params) => {
    const rows = document.querySelectorAll('tr.parametro');
    for (const row of rows) {
        const labelCell = row.querySelector('td:first-child');
        const labelText = labelCell?.innerText?.trim();
        if (!labelText || !labelText.toLowerCase().includes(params.f.toLowerCase())) {
            continue;
        }
        const input = row.querySelector('input');
        const select = row.querySelector('select');
        const control = input || select;
        if (!control) continue;

        const prev = input ? input.value : (select.options[select.selectedIndex]?.text || '');

        if (input) {
            input.value = params.v;
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
        } else if (select) {
            let found = false;
            for (const opt of select.options) {
                if (opt.text.toLowerCase().includes(params.v.toLowerCase())) {
                    select.value = opt.value;
                    select.dispatchEvent(new Event('change', {bubbles: true}));
                    found = true;
                    break;
                }
            }
            if (!found) {
                return {err: 'Option not found: ' + params.v + ' in field ' + params.f};
            }
        }

        control.classList.add('ai-modified');
        row.classList.add('ai-modified-row');

        const existingBadge = control.parentNode.querySelector('.ai-change-badge');
        if (!existingBadge) {
            const indicator = document.createElement('span');
            indicator.className = 'ai-change-badge';
            indicator.textContent = prev + ' → ' + params.v;
            control.parentNode.appendChild(indicator);
        }

        control.scrollIntoView({behavior: 'smooth', block: 'center'});
        return {field: labelText, prev: prev, new: params.v};
    }
    return {err: 'Field not found: ' + params.f};
}
"""


def set_browser(browser: BrowserManager):
    """Set the browser instance for tools to use."""
    global _browser
    _browser = browser


def get_active_tabs() -> Dict[str, Any]:
    """Get all active tabs (for backwards compatibility)."""
    return {**_results_tabs, **{str(k): v for k, v in _order_tabs.items()}}


async def _inject_highlight_styles(page):
    """Inject CSS for highlighting modified fields."""
    await page.evaluate(f"""
        () => {{
            if (document.getElementById('ai-styles')) return;
            const style = document.createElement('style');
            style.id = 'ai-styles';
            style.textContent = `{HIGHLIGHT_STYLES}`;
            document.head.appendChild(style);
        }}
    """)


def close_all_tabs():
    """Close all active tabs."""
    global _results_tabs, _order_tabs
    _results_tabs.clear()
    _order_tabs.clear()


def reset_tab_state():
    """Reset tab state tracking (call on new conversation)."""
    global _tab_state_manager
    _tab_state_manager.reset()


def get_tab_state_manager() -> TabStateManager:
    """Get the global tab state manager."""
    return _tab_state_manager


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _extract_order_num_from_url(url: str) -> Optional[str]:
    """Extract order number from reportes2 URL."""
    match = re.search(r'numeroOrden=(\d+)', url)
    return match.group(1) if match else None


def _extract_order_id_from_url(url: str) -> Optional[int]:
    """Extract order ID from ordenes/edit URL."""
    match = re.search(r'/ordenes/(\d+)/edit', url)
    return int(match.group(1)) if match else None


async def _find_or_create_results_tab(order_num: str) -> Any:
    """Find existing results tab by order number or create new one."""
    global _results_tabs

    # Check if we have this tab tracked
    if order_num in _results_tabs:
        page = _results_tabs[order_num]
        try:
            # Verify tab is still valid
            _ = page.url
            return page
        except Exception:
            # Tab is invalid, remove from tracking
            del _results_tabs[order_num]

    # Search through all browser tabs
    for page in _browser.context.pages:
        url = page.url
        if '/reportes2' in url:
            extracted = _extract_order_num_from_url(url)
            if extracted == order_num:
                _results_tabs[order_num] = page
                return page

    # Create new tab
    await _browser.ensure_browser()  # Auto-restart if browser was closed
    page = await _browser.context.new_page()
    url = f"https://laboratoriofranz.orion-labs.com/reportes2?numeroOrden={order_num}"
    await page.goto(url, timeout=30000)

    # Wait for network to settle (AJAX data loading)
    try:
        await page.wait_for_load_state('networkidle', timeout=10000)
    except Exception:
        # Fallback to brief wait if networkidle times out
        await page.wait_for_timeout(1000)

    await _inject_highlight_styles(page)
    _results_tabs[order_num] = page
    return page


async def _find_order_tab_by_index(tab_index: int) -> Any:
    """Find an order tab (nueva_orden or orden_edit) by its index in the browser."""
    await _browser.ensure_browser()  # Auto-restart if browser was closed
    pages = _browser.context.pages
    if tab_index < 0 or tab_index >= len(pages):
        raise ValueError(f"Tab index {tab_index} out of range (0-{len(pages)-1})")

    page = pages[tab_index]
    url = page.url

    if '/ordenes/create' in url or ('/ordenes/' in url and '/edit' in url):
        return page
    else:
        raise ValueError(f"Tab {tab_index} is not an order tab (URL: {url})")


async def _find_or_create_order_tab(order_id: int) -> Any:
    """Find existing order edit tab by order ID or create new one."""
    global _order_tabs

    # Check if we have this tab tracked
    if order_id in _order_tabs:
        page = _order_tabs[order_id]
        try:
            # Verify tab is still valid
            _ = page.url
            return page
        except Exception:
            # Tab is invalid, remove from tracking
            del _order_tabs[order_id]

    # Search through all browser tabs
    for page in _browser.context.pages:
        url = page.url
        if '/ordenes/' in url and '/edit' in url:
            extracted = _extract_order_id_from_url(url)
            if extracted == order_id:
                _order_tabs[order_id] = page
                return page

    # Create new tab
    await _browser.ensure_browser()  # Auto-restart if browser was closed
    page = await _browser.context.new_page()
    url = f"https://laboratoriofranz.orion-labs.com/ordenes/{order_id}/edit"
    await page.goto(url, timeout=30000)

    # Wait for network to settle (AJAX data loading for exams list)
    try:
        await page.wait_for_load_state('networkidle', timeout=10000)
    except Exception:
        # Fallback to brief wait if networkidle times out
        await page.wait_for_timeout(1000)

    _order_tabs[order_id] = page
    return page


async def _extract_tab_state(page, tab_type: str) -> dict:
    """Extract detailed state from a tab based on its type."""
    state = {}

    try:
        if tab_type == "resultados":
            # Wait for the results page to fully load (has exam rows with inputs/selects)
            try:
                await page.wait_for_selector('tr.examen', timeout=5000)
                # Also wait a bit for AJAX content
                await page.wait_for_timeout(500)
            except Exception:
                # Page might not have loaded yet or structure is different
                logger.warning(f"Results page may not have loaded: {page.url}")

            # Extract results page state
            data = await page.evaluate(EXTRACT_REPORTES_JS)
            state["paciente"] = data.get("paciente")
            state["order_num"] = data.get("numero_orden")
            # Extract exam field values with dropdown options
            examenes = data.get("examenes", [])
            state["examenes_count"] = len(examenes)
            # Track field values for change detection
            field_values = {}
            # Full field details with dropdown options
            fields_details = []
            for exam in examenes:
                exam_name = exam.get("nombre", "")
                for campo in exam.get("campos", []):
                    field_name = campo.get("f", "")
                    field_key = f"{exam_name}:{field_name}"
                    field_values[field_key] = campo.get("val", "")
                    # Include full field details
                    fields_details.append({
                        "key": field_key,
                        "exam": exam_name,
                        "field": field_name,
                        "value": campo.get("val", ""),
                        "type": campo.get("tipo", "input"),
                        "options": campo.get("opciones"),  # Dropdown options
                        "ref": campo.get("ref")  # Reference values
                    })
            state["field_values"] = field_values
            state["fields_details"] = fields_details
            logger.debug(f"Results extraction: {len(examenes)} exams, {len(fields_details)} fields")

        elif tab_type == "orden_edit":
            # Extract order edit page state
            data = await page.evaluate(EXTRACT_ORDEN_EDIT_JS)
            state["paciente"] = data.get("paciente", {}).get("nombres") if isinstance(data.get("paciente"), dict) else data.get("paciente")
            added_exams = await page.evaluate(EXTRACT_ADDED_EXAMS_JS)
            state["exams"] = [e.get("codigo") for e in added_exams]
            # Include full exam details with prices
            state["exams_details"] = [{
                "codigo": e.get("codigo"),
                "nombre": e.get("nombre"),
                "valor": e.get("valor"),  # Price
                "estado": e.get("estado"),
                "can_remove": e.get("can_remove", False)
            } for e in added_exams]
            state["exams_count"] = len(added_exams)
            # Get total
            totals = await page.evaluate(r"""
                () => {
                    let total = null;
                    document.querySelectorAll('.fw-bold, .fs-5, .text-end').forEach(el => {
                        const text = el.innerText?.trim() || '';
                        if (text.startsWith('$') && !total) total = text;
                    });
                    return { total };
                }
            """)
            state["total"] = totals.get("total")

        elif tab_type == "nueva_orden":
            # Extract new order page state
            added_exams = await page.evaluate(EXTRACT_ADDED_EXAMS_JS)
            state["exams"] = [e.get("codigo") for e in added_exams]
            # Include full exam details with prices
            state["exams_details"] = [{
                "codigo": e.get("codigo"),
                "nombre": e.get("nombre"),
                "valor": e.get("valor"),  # Price
                "estado": e.get("estado"),
                "can_remove": e.get("can_remove", False)
            } for e in added_exams]
            state["exams_count"] = len(added_exams)
            # Get total
            totals = await page.evaluate(r"""
                () => {
                    let total = null;
                    document.querySelectorAll('.fw-bold, .fs-5, .text-end').forEach(el => {
                        const text = el.innerText?.trim() || '';
                        if (text.startsWith('$') && !total) total = text;
                    });
                    return { total };
                }
            """)
            state["total"] = totals.get("total")

    except Exception as e:
        state["error"] = str(e)

    return state


async def _get_all_tabs_info() -> dict:
    """
    Get info about all open browser tabs with state tracking.

    Returns:
        - tabs: List of tab info with state and changes
        - Each tab includes: type, id, paciente, is_new, changes (if any)
        - Duplicate tabs are enumerated
    """
    global _tab_state_manager

    if not _browser:
        return {"error": "Browser not available", "tabs": []}

    await _browser.ensure_browser()  # Auto-restart if browser was closed
    pages = _browser.context.pages
    tabs_info = []
    current_tab_keys = set()

    # Count tabs by ID to detect duplicates
    id_counts: Dict[str, int] = {}
    id_indices: Dict[str, int] = {}

    # First pass: count duplicates
    for page in pages:
        url = page.url
        tab_type = "unknown"
        tab_id = None

        if '/ordenes/create' in url:
            tab_type = "nueva_orden"
        elif '/ordenes/' in url and '/edit' in url:
            tab_type = "orden_edit"
            tab_id = _extract_order_id_from_url(url)
        elif '/reportes2' in url:
            tab_type = "resultados"
            tab_id = _extract_order_num_from_url(url)

        if tab_id:
            key = f"{tab_type}:{tab_id}"
            id_counts[key] = id_counts.get(key, 0) + 1

    # Second pass: build tab info with enumeration
    for i, page in enumerate(pages):
        url = page.url
        tab_key = _tab_state_manager._get_tab_key(url, i)
        current_tab_keys.add(tab_key)

        tab_info = {
            "index": i,
            "type": "unknown",
            "id": None,
            "paciente": None,
            "is_new": _tab_state_manager.is_new_tab(tab_key),
            "active": page == _browser.page
        }

        # Determine tab type and extract ID
        if '/ordenes/create' in url:
            tab_info["type"] = "nueva_orden"
        elif '/ordenes/' in url and '/edit' in url:
            tab_info["type"] = "orden_edit"
            tab_info["id"] = _extract_order_id_from_url(url)
        elif '/ordenes' in url and '/ordenes/' not in url:
            tab_info["type"] = "ordenes_list"
        elif '/reportes2' in url:
            tab_info["type"] = "resultados"
            tab_info["id"] = _extract_order_num_from_url(url)
        elif '/login' in url:
            tab_info["type"] = "login"

        # Add enumeration for duplicates
        if tab_info["id"]:
            dup_key = f"{tab_info['type']}:{tab_info['id']}"
            if id_counts.get(dup_key, 0) > 1:
                id_indices[dup_key] = id_indices.get(dup_key, 0) + 1
                tab_info["instance"] = id_indices[dup_key]

        # Extract detailed state for relevant tabs
        if tab_info["type"] in ["resultados", "orden_edit", "nueva_orden"]:
            current_state = await _extract_tab_state(page, tab_info["type"])
            tab_info["paciente"] = current_state.get("paciente")

            # Get known state and compute delta
            known_state = _tab_state_manager.get_known_state(tab_key)

            # Always include full state for tabs that need detailed info
            tab_info["state"] = current_state

            if not tab_info["is_new"]:
                # For known tabs, also include changes
                delta = _tab_state_manager.compute_state_delta(known_state or {}, current_state)
                if delta:
                    tab_info["changes"] = delta

            # Update known state
            _tab_state_manager.update_known_state(tab_key, current_state)

        tabs_info.append(tab_info)

    # Clean up closed tabs
    _tab_state_manager.clear_closed_tabs(current_tab_keys)

    return {"tabs": tabs_info, "total": len(tabs_info)}


# ============================================================
# ASYNC TOOL IMPLEMENTATIONS
# ============================================================

async def _search_orders_impl(
    search: str = "",
    limit: int = 20,
    page_num: int = 1,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None
) -> dict:
    """Internal async implementation of search_orders."""
    from urllib.parse import urlencode

    logger.info(f"[search_orders] Searching: '{search}', page={page_num}")

    params = {"page": page_num}
    if search:
        params["cadenaBusqueda"] = search
    if fecha_desde:
        params["fechaDesde"] = fecha_desde
    if fecha_hasta:
        params["fechaHasta"] = fecha_hasta

    url = f"https://laboratoriofranz.orion-labs.com/ordenes?{urlencode(params)}"
    await _browser.ensure_browser()  # Auto-restart if browser was closed
    temp_page = await _browser.context.new_page()

    try:
        await temp_page.goto(url, timeout=30000)
        try:
            await temp_page.wait_for_load_state('networkidle', timeout=10000)
        except Exception:
            await temp_page.wait_for_timeout(1000)

        ordenes = await temp_page.evaluate(EXTRACT_ORDENES_JS)
        logger.info(f"[search_orders] Found {len(ordenes)} orders")

        return {
            "ordenes": ordenes[:limit],
            "total": len(ordenes[:limit]),
            "page": page_num,
            "filters": {"search": search or None, "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta},
            "tip": "Use 'num' field for get_order_results(), use 'id' field for get_order_info() or edit_order_exams()"
        }
    finally:
        # Clean up temp page (only if browser is still alive)
        try:
            pages = _browser.context.pages
            if len(pages) > 1:
                await temp_page.close()
        except Exception:
            pass  # Browser was closed, nothing to clean up


async def _get_order_results_impl(order_nums: List[str] = None, tab_indices: List[int] = None) -> dict:
    """
    Get exam result fields for orders. Opens/reuses reportes2 tabs.
    Returns exam fields ready for edit_results().

    Args:
        order_nums: List of order numbers to fetch results for (opens/reuses tabs)
        tab_indices: List of tab indices to read from (for already-opened tabs)
    """
    import asyncio
    results = []

    # Process by tab_indices (read from already-opened tabs)
    if tab_indices:
        logger.info(f"[get_order_results] Reading from {len(tab_indices)} tab(s) by index...")
        await _browser.ensure_browser()
        pages = _browser.context.pages

        for tab_idx in tab_indices:
            try:
                if tab_idx < 0 or tab_idx >= len(pages):
                    results.append({"tab_index": tab_idx, "error": f"Tab index {tab_idx} out of range (0-{len(pages)-1})"})
                    continue

                page = pages[tab_idx]
                url = page.url

                # Check if it's a results tab
                if '/reportes2' not in url:
                    results.append({"tab_index": tab_idx, "error": f"Tab {tab_idx} is not a results tab (URL: {url})"})
                    continue

                order_num = _extract_order_num_from_url(url)
                await page.bring_to_front()

                data = await page.evaluate(EXTRACT_REPORTES_JS)
                exam_count = len(data.get('examenes', []))
                logger.info(f"[get_order_results] Tab {tab_idx} (order {order_num}): {exam_count} exams")

                results.append({
                    "tab_index": tab_idx,
                    "order_num": order_num,
                    "tab_ready": True,
                    **data
                })
            except Exception as e:
                logger.error(f"[get_order_results] Error for tab {tab_idx}: {e}")
                results.append({"tab_index": tab_idx, "tab_ready": False, "error": str(e)})

    # Process by order_nums (opens/reuses tabs by order number)
    if order_nums:
        logger.info(f"[get_order_results] Getting results for {len(order_nums)} orders...")

        async def process_order(order_num: str) -> dict:
            try:
                page = await _find_or_create_results_tab(order_num)
                await page.bring_to_front()

                data = await page.evaluate(EXTRACT_REPORTES_JS)
                exam_count = len(data.get('examenes', []))
                logger.info(f"[get_order_results] Order {order_num}: {exam_count} exams")

                return {
                    "order_num": order_num,
                    "tab_ready": True,
                    **data
                }
            except Exception as e:
                logger.error(f"[get_order_results] Error for order {order_num}: {e}")
                return {"order_num": order_num, "tab_ready": False, "error": str(e)}

        order_results = await asyncio.gather(*[process_order(num) for num in order_nums])
        results.extend(order_results)

    if not results:
        return {
            "error": "No order_nums or tab_indices provided",
            "hint": "Use order_nums=['2601068'] or tab_indices=[1] from CONTEXT tabs"
        }

    return {
        "orders": results,
        "total": len(results),
        "tip": "Use edit_results() with order_num to edit these results."
    }


async def _get_order_info_impl(order_ids: List[int] = None, tab_indices: List[int] = None) -> dict:
    """
    Get order info (patient, exams, totals). Opens/reuses ordenes/edit tabs.
    Returns order details ready for edit_order_exams().

    Args:
        order_ids: List of order IDs to fetch info for (opens/reuses tabs)
        tab_indices: List of tab indices to read from (for already-opened order/create tabs)
    """
    import asyncio
    results = []

    # Process by tab_indices (read from already-opened tabs)
    if tab_indices:
        logger.info(f"[get_order_info] Reading from {len(tab_indices)} tab(s) by index...")
        await _browser.ensure_browser()
        pages = _browser.context.pages

        for tab_idx in tab_indices:
            try:
                if tab_idx < 0 or tab_idx >= len(pages):
                    results.append({"tab_index": tab_idx, "error": f"Tab index {tab_idx} out of range (0-{len(pages)-1})"})
                    continue

                page = pages[tab_idx]
                url = page.url

                # Check if it's an order tab (edit or create)
                if '/ordenes/' not in url or ('/ordenes/' in url and '/edit' not in url and '/create' not in url):
                    # Check if it's at least an ordenes page
                    if '/ordenes/create' not in url and '/ordenes/' not in url:
                        results.append({"tab_index": tab_idx, "error": f"Tab {tab_idx} is not an order tab (URL: {url})"})
                        continue

                order_id = _extract_order_id_from_url(url)
                await page.bring_to_front()

                data = await page.evaluate(EXTRACT_ORDEN_EDIT_JS)
                data["tab_index"] = tab_idx
                if order_id:
                    data["order_id"] = order_id

                # Also get added exams with details
                added_exams = await page.evaluate(EXTRACT_ADDED_EXAMS_JS)
                data["exams"] = added_exams

                logger.info(f"[get_order_info] Tab {tab_idx} (order {order_id or 'new'}): {len(added_exams)} exams")
                results.append(data)
            except Exception as e:
                logger.error(f"[get_order_info] Error for tab {tab_idx}: {e}")
                results.append({"tab_index": tab_idx, "error": str(e)})

    # Process by order_ids (opens/reuses tabs by order ID)
    if order_ids:
        logger.info(f"[get_order_info] Getting info for {len(order_ids)} orders...")

        async def process_order(order_id: int) -> dict:
            try:
                page = await _find_or_create_order_tab(order_id)
                await page.bring_to_front()

                data = await page.evaluate(EXTRACT_ORDEN_EDIT_JS)
                data["order_id"] = order_id

                # Also get added exams with details
                added_exams = await page.evaluate(EXTRACT_ADDED_EXAMS_JS)
                data["exams"] = added_exams

                logger.info(f"[get_order_info] Order {order_id}: {len(added_exams)} exams")
                return data
            except Exception as e:
                logger.error(f"[get_order_info] Error for order {order_id}: {e}")
                return {"order_id": order_id, "error": str(e)}

        order_results = await asyncio.gather(*[process_order(oid) for oid in order_ids])
        results.extend(order_results)

    if not results:
        return {
            "error": "No order_ids or tab_indices provided",
            "hint": "Use order_ids=[123] or tab_indices=[1] from CONTEXT tabs"
        }

    return {
        "orders": results,
        "total": len(results),
        "tip": "Use edit_order_exams() with order_id or tab_index to add/remove exams."
    }


async def _edit_results_impl(data: List[Dict[str, str]]) -> dict:
    """Edit exam result fields. Finds tabs by order_num, tab_index, or creates new ones."""
    logger.info(f"[edit_results] Editing {len(data)} fields")

    # Validate input - ensure required fields are present (either orden or tab_index)
    for i, item in enumerate(data):
        has_orden = "orden" in item
        has_tab_index = "tab_index" in item
        if not has_orden and not has_tab_index:
            return {
                "error": f"Item {i} missing orden or tab_index",
                "hint": "Each item needs: (orden OR tab_index), e (exam name), f (field name), v (value)",
                "received": item
            }
        missing = [f for f in ["e", "f", "v"] if f not in item]
        if missing:
            return {
                "error": f"Item {i} missing required fields: {missing}",
                "hint": "Each item needs: (orden OR tab_index), e (exam name), f (field name), v (value)",
                "suggestion": "Use get_order_results(order_nums) or get_order_results(tab_indices) first",
                "received": item
            }

    results = []
    results_by_order = {}

    # Cache for tab_index -> page mapping
    tab_pages = {}

    for item in data:
        order_num = item.get("orden")
        tab_index = item.get("tab_index")

        # Find or create the tab
        try:
            if tab_index is not None:
                # Use tab_index to find the page
                if tab_index not in tab_pages:
                    await _browser.ensure_browser()
                    pages = _browser.context.pages
                    if tab_index < 0 or tab_index >= len(pages):
                        results.append({"tab_index": tab_index, "err": f"Tab index {tab_index} out of range (0-{len(pages)-1})"})
                        continue
                    page = pages[tab_index]
                    url = page.url
                    if '/reportes2' not in url:
                        results.append({"tab_index": tab_index, "err": f"Tab {tab_index} is not a results tab (URL: {url})"})
                        continue
                    # Extract order_num from URL for logging
                    order_num = _extract_order_num_from_url(url)
                    tab_pages[tab_index] = (page, order_num)
                page, order_num = tab_pages[tab_index]
            else:
                # Use order_num to find/create the page
                page = await _find_or_create_results_tab(order_num)

            await page.bring_to_front()

            result = await page.evaluate(FILL_FIELD_JS, {
                "e": item["e"],
                "f": item["f"],
                "v": item["v"]
            })
            result["orden"] = order_num
            if tab_index is not None:
                result["tab_index"] = tab_index
            results.append(result)
            logger.info(f"[edit_results] {order_num}/{item['f']}: {result}")
        except Exception as e:
            error_result = {"err": str(e)}
            if order_num:
                error_result["orden"] = order_num
            if tab_index is not None:
                error_result["tab_index"] = tab_index
            results.append(error_result)

        # Track results by order
        key = order_num or f"tab_{tab_index}"
        if key not in results_by_order:
            results_by_order[key] = {"filled": 0, "errors": 0}
        if "field" in results[-1]:
            results_by_order[key]["filled"] += 1
        if "err" in results[-1]:
            results_by_order[key]["errors"] += 1

    filled = len([r for r in results if "field" in r])
    errors = [r for r in results if "err" in r]

    return {
        "filled": filled,
        "total": len(data),
        "by_order": results_by_order,
        "details": results,
        "errors": errors,
        "next_step": "Revisa los campos resaltados y haz click en 'Guardar' en cada pestaña."
    }


async def _edit_order_exams_impl(
    order_id: Optional[int] = None,
    tab_index: Optional[int] = None,
    add: Optional[List[str]] = None,
    remove: Optional[List[str]] = None,
    cedula: Optional[str] = None
) -> dict:
    """
    Edit an order: add/remove exams and/or set cedula.
    Use order_id for existing orders, or tab_index for new orders (ordenes/create tabs).
    """
    add = add or []
    remove = remove or []

    # Determine which page to use
    if tab_index is not None:
        logger.info(f"[edit_order_exams] Editing tab {tab_index}: add={len(add)}, remove={len(remove)}, cedula={cedula}")
        try:
            page = await _find_order_tab_by_index(tab_index)
        except ValueError as e:
            return {"error": str(e)}
        identifier = f"tab_{tab_index}"
        is_new_order = '/ordenes/create' in page.url
    elif order_id is not None:
        logger.info(f"[edit_order_exams] Editing order {order_id}: add={len(add)}, remove={len(remove)}, cedula={cedula}")
        page = await _find_or_create_order_tab(order_id)
        identifier = f"order_{order_id}"
        is_new_order = False
    else:
        return {"error": "Either order_id or tab_index must be provided"}

    await page.bring_to_front()

    # Dismiss any notification popups that might block interactions
    await _browser.dismiss_popups()

    result = {
        "identifier": identifier,
        "tab_index": tab_index,
        "order_id": order_id,
        "is_new_order": is_new_order,
        "added": [],
        "removed": [],
        "failed_add": [],
        "failed_remove": [],
        "cedula_updated": False
    }

    try:
        # Update cedula if provided
        if cedula is not None:
            cedula_input = page.locator('#identificacion')
            if await cedula_input.count() > 0:
                await cedula_input.fill(cedula)
                await page.wait_for_timeout(500)
                # Trigger search/validation if there's a button
                search_btn = page.locator('button:has-text("Buscar"), button[title*="Buscar"]')
                if await search_btn.count() > 0:
                    await search_btn.first.click()
                    await page.wait_for_timeout(1000)
                result["cedula_updated"] = True
                result["cedula"] = cedula
                logger.info(f"[edit_order_exams] Updated cedula to: {cedula}")
            else:
                result["cedula_error"] = "Cedula input not found"

        # Remove exams
        if remove:
            remove_upper = [code.upper().strip() for code in remove]
            current_exams = await page.evaluate(EXTRACT_ADDED_EXAMS_JS)

            for exam_code in remove_upper:
                found = False
                for exam in current_exams:
                    if exam.get('codigo', '').upper() == exam_code:
                        found = True
                        try:
                            removed = await page.evaluate(f"""
                                () => {{
                                    const container = document.querySelector('#examenes-seleccionados');
                                    if (!container) return {{ error: 'Container not found' }};
                                    const rows = container.querySelectorAll('tbody tr');
                                    for (const row of rows) {{
                                        const cellText = row.querySelector('td')?.innerText || '';
                                        if (cellText.toUpperCase().includes('{exam_code}')) {{
                                            const removeBtn = row.querySelector('button[title*="Quitar"], button.btn-danger, button.btn-outline-danger');
                                            if (removeBtn) {{
                                                removeBtn.click();
                                                return {{ removed: true }};
                                            }}
                                            return {{ error: 'Remove button not found' }};
                                        }}
                                    }}
                                    return {{ error: 'Exam not found' }};
                                }}
                            """)
                            if removed.get('removed'):
                                result["removed"].append(exam_code)
                                await page.wait_for_timeout(300)
                            else:
                                result["failed_remove"].append({'codigo': exam_code, 'reason': removed.get('error')})
                        except Exception as e:
                            result["failed_remove"].append({'codigo': exam_code, 'reason': str(e)})
                        break
                if not found:
                    result["failed_remove"].append({'codigo': exam_code, 'reason': 'not in order'})

        # Add exams
        if add:
            search = page.locator('#buscar-examen-input')
            for exam_code in add:
                exam_code_upper = exam_code.upper().strip()
                await search.fill('')
                await search.fill(exam_code_upper)
                # Wait for search results (reduced from 1000ms)
                await page.wait_for_timeout(400)

                available = await page.evaluate(EXTRACT_AVAILABLE_EXAMS_JS)
                matched_exam = None
                for exam in available:
                    if exam.get('codigo') and exam['codigo'].upper() == exam_code_upper:
                        matched_exam = exam
                        break

                if matched_exam:
                    button_id = matched_exam['button_id']
                    btn = page.locator(f'#{button_id}')
                    try:
                        await btn.click(timeout=2000)
                        result["added"].append(exam_code_upper)
                    except Exception as e:
                        result["failed_add"].append({'codigo': exam_code_upper, 'reason': str(e)})
                else:
                    result["failed_add"].append({'codigo': exam_code_upper, 'reason': 'no exact match'})

        # Get updated state
        await page.wait_for_timeout(300)
        current_exams = await page.evaluate(EXTRACT_ADDED_EXAMS_JS)
        totals = await page.evaluate(r"""
            () => {
                const result = { total: null };
                document.querySelectorAll('.fw-bold, .fs-5, .text-end').forEach(el => {
                    const text = el.innerText?.trim() || '';
                    if (text.startsWith('$') && !result.total) result.total = text;
                });
                return result;
            }
        """)

        result["current_exams"] = current_exams
        result["totals"] = totals
        result["status"] = "pending_save"
        result["next_step"] = "Revisa los cambios y haz click en 'Guardar'."

    except Exception as e:
        logger.error(f"[edit_order_exams] Error: {e}")
        result["error"] = str(e)

    return result


async def _create_order_impl(cedula: str, exams: List[str]) -> dict:
    """Create a new order with exams. Adds exams FIRST, then cedula to avoid popup blocking."""
    is_cotizacion = not cedula or cedula.strip() == ""
    logger.info(f"[create_order] Creating {'cotización' if is_cotizacion else 'order'} with {len(exams)} exams: {exams}")

    # Use get_page_for_new_order to preserve existing cotización tabs
    page = await _browser.get_page_for_new_order()
    await page.goto("https://laboratoriofranz.orion-labs.com/ordenes/create")

    # Wait for page to load and exams table to be ready
    await page.wait_for_load_state('networkidle', timeout=10000)

    # Dismiss any notification popups that might block interactions
    await _browser.dismiss_popups()

    # FIRST: Add all exams (before cedula to avoid "new patient" popup blocking buttons)
    added_codes = []
    failed_exams = []

    # Click exam buttons - must re-extract available exams after each click
    # because clicking removes the exam from available list and shifts button IDs
    for i, exam_code in enumerate(exams):
        exam_code_upper = exam_code.upper().strip()

        # Dismiss popups every 5 exams (they can appear mid-process)
        if i > 0 and i % 5 == 0:
            await _browser.dismiss_popups()

        # Extract current available exams (IDs shift after each click)
        available = await page.evaluate(EXTRACT_AVAILABLE_EXAMS_JS)

        # Find button ID for this exam
        button_id = None
        for exam in available:
            if exam.get('codigo') and exam['codigo'].upper() == exam_code_upper:
                button_id = exam['button_id']
                break

        if button_id:
            btn = page.locator(f'#{button_id}')
            try:
                # Click with Playwright's auto-waiting (waits for actionable)
                # Button stays visible after click (exam added to selected list)
                await btn.click()
                added_codes.append(exam_code_upper)
            except Exception as e:
                logger.warning(f"[create_order] Failed to click {exam_code_upper}: {e}")
                failed_exams.append({'codigo': exam_code_upper, 'reason': str(e)})
        else:
            failed_exams.append({'codigo': exam_code_upper, 'reason': 'not found'})

    # Get the final list of added exams and totals
    added_exams = await page.evaluate(EXTRACT_ADDED_EXAMS_JS)

    totals = await page.evaluate(r"""
        () => {
            const result = { total: null };
            document.querySelectorAll('.fw-bold, .fs-5, .text-end').forEach(el => {
                const text = el.innerText?.trim() || '';
                if (text.startsWith('$') && !result.total) result.total = text;
            });
            return result;
        }
    """)

    logger.info(f"[create_order] Added {len(added_codes)}/{len(exams)} exams{f', {len(failed_exams)} failed' if failed_exams else ''}")

    # THEN: Add cedula (after exams are added)
    new_patient_detected = False
    if not is_cotizacion:
        cedula_input = page.locator('#identificacion')
        await cedula_input.fill(cedula)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1500)

        # Check if "Crear paciente" popup appeared (new patient)
        new_patient_modal = page.locator('#gestionar-paciente-modal')
        if await new_patient_modal.count() > 0:
            # Check if modal is visible (has "show" class and display: block)
            is_visible = await new_patient_modal.evaluate("""
                el => el.classList.contains('show') && getComputedStyle(el).display !== 'none'
            """)
            if is_visible:
                new_patient_detected = True
                logger.info(f"[create_order] New patient popup detected for cedula {cedula}")

                # Close the modal
                close_btn = page.locator('#gestionar-paciente-modal button[data-bs-dismiss="modal"]').first
                if await close_btn.count() > 0:
                    await close_btn.click()
                    await page.wait_for_timeout(500)

    result = {
        "cedula": cedula if not is_cotizacion else None,
        "is_cotizacion": is_cotizacion,
        "exams_added": [{"codigo": e.get('codigo'), "nombre": e.get('nombre'), "precio": e.get('valor')} for e in added_exams],
        "exams_failed": failed_exams,
        "totals": totals,
    }

    if new_patient_detected:
        result["status"] = "new_patient_required"
        result["new_patient"] = True
        result["next_step"] = f"El paciente con cédula {cedula} no existe en el sistema. Debes crear el paciente primero antes de guardar la orden. Los exámenes ya están agregados con un total de {totals.get('total', 'N/A')}."
    elif is_cotizacion:
        result["status"] = "cotizacion"
        result["next_step"] = "Esta es solo una cotización (sin paciente)."
    else:
        result["status"] = "pending_save"
        result["next_step"] = "Revisa los exámenes y haz click en 'Guardar' para confirmar."

    return result


async def _get_available_exams_impl(order_id: Optional[int] = None) -> dict:
    """Get list of available exams."""
    logger.info(f"[get_available_exams] order_id={order_id}")

    if order_id:
        page = await _find_or_create_order_tab(order_id)
    else:
        page = await _browser.ensure_page()
        await page.goto("https://laboratoriofranz.orion-labs.com/ordenes/create", timeout=30000)
        await page.wait_for_timeout(1500)

    available = await page.evaluate(EXTRACT_AVAILABLE_EXAMS_JS)
    added = await page.evaluate(EXTRACT_ADDED_EXAMS_JS) if order_id else []

    return {
        "order_id": order_id,
        "available_exams": available,
        "total_available": len(available),
        "added_exams": added,
        "total_added": len(added)
    }


# ============================================================
# TOOL DEFINITIONS
# ============================================================

@tool
async def search_orders(
    search: str = "",
    limit: int = 20,
    page_num: int = 1,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None
) -> str:
    """Search orders by patient name. Returns 'num' and 'id' for each order. Uses fuzzy search fallback if no exact matches."""
    result = await _search_orders_impl(search, limit, page_num, fecha_desde, fecha_hasta)

    # If no results and there's a search term, try fuzzy search
    if search and (not result.get("ordenes") or len(result.get("ordenes", [])) == 0):
        logger.info(f"[search_orders] No exact matches for '{search}', trying fuzzy search...")
        fuzzy_results = fuzzy_search_patient(search, min_score=70, max_results=10)

        if fuzzy_results:
            logger.info(f"[search_orders] Fuzzy search found {len(fuzzy_results)} matches:")
            for r in fuzzy_results[:3]:  # Log first 3 matches
                logger.info(f"  -> {r['patient_name']} ({r['similarity_score']}%) - Ord. {r['order_num']}")
            result["fuzzy_fallback"] = True
            result["fuzzy_suggestions"] = fuzzy_results
            result["fuzzy_message"] = format_fuzzy_results(fuzzy_results, search)
        else:
            logger.warning(f"[search_orders] Fuzzy search returned no results (is orders cache empty?)")
            result["fuzzy_fallback"] = True
            result["fuzzy_suggestions"] = []
            result["fuzzy_message"] = f"No se encontraron coincidencias para '{search}'. Nota: El caché de órdenes puede estar vacío - usa 'Actualizar lista de órdenes' en el panel de admin."

    return json.dumps(result, ensure_ascii=False)


@tool
async def get_order_results(
    order_nums: List[str] = None,
    tab_indices: List[int] = None
) -> str:
    """Get result fields for orders. Use order_nums to open by order number, or tab_indices to read from already-opened tabs (from CONTEXT). BATCH: pass ALL at once."""
    result = await _get_order_results_impl(order_nums=order_nums, tab_indices=tab_indices)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_order_info(
    order_ids: List[int] = None,
    tab_indices: List[int] = None
) -> str:
    """Get order details and exams list. Use order_ids to open by ID, or tab_indices to read from already-opened order/create tabs (from CONTEXT). BATCH: pass ALL at once."""
    result = await _get_order_info_impl(order_ids=order_ids, tab_indices=tab_indices)
    return json.dumps(result, ensure_ascii=False)


class EditResultsInput(BaseModel):
    """Input schema for edit_results."""
    data: List[Dict[str, str]] = Field(
        description="List of edits. Each: (orden OR tab_index), e (exam name), f (field name), v (value). Use tab_index from CONTEXT tabs."
    )


@tool(args_schema=EditResultsInput)
async def edit_results(data: List[Dict[str, str]]) -> str:
    """Edit result fields. BATCH all: data=[{orden OR tab_index, e (exam), f (field), v (value)}]. Use tab_index from CONTEXT tabs."""
    result = await _edit_results_impl(data)
    return json.dumps(result, ensure_ascii=False)


@tool
async def edit_order_exams(
    order_id: Optional[int] = None,
    tab_index: Optional[int] = None,
    add: Optional[List[str]] = None,
    remove: Optional[List[str]] = None,
    cedula: Optional[str] = None
) -> str:
    """Edit order: add/remove exams, set cedula. Use order_id for saved orders, tab_index for new orders (from CONTEXT tabs)."""
    result = await _edit_order_exams_impl(order_id, tab_index, add, remove, cedula)
    return json.dumps(result, ensure_ascii=False)


@tool
async def create_new_order(cedula: str, exams: List[str]) -> str:
    """Create order. cedula="" for cotización. exams=["BH","EMO"]"""
    result = await _create_order_impl(cedula, exams)
    return json.dumps(result, ensure_ascii=False)


@tool
def ask_user(message: str, options: Optional[List[str]] = None) -> str:
    """Display message with clickable options to the user. After calling this tool, you MUST stop and respond to the user with the message. Do NOT call any other tools after ask_user - just respond and wait for user input."""
    result = {
        "message": message,
        "status": "waiting_for_user"
    }
    if options:
        result["options"] = options
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_available_exams(order_id: Optional[int] = None) -> str:
    """Get available exam codes. If order_id given, also returns added exams."""
    result = await _get_available_exams_impl(order_id)
    return json.dumps(result, ensure_ascii=False)


# Global variable to store the current chat_id for set_chat_title
_current_chat_id: Optional[str] = None


def set_current_chat_id(chat_id: str) -> None:
    """Set the current chat ID for the set_chat_title tool to use."""
    global _current_chat_id
    _current_chat_id = chat_id


@tool
def set_chat_title(title: str) -> str:
    """
    Set a descriptive title for this chat conversation.

    IMPORTANT: Call this tool on your FIRST response in a new chat to give the conversation
    a meaningful title. You can call this alongside other tools or with your final response.

    RULES:
    - Title must be 2-5 words in Spanish
    - Describe the main topic/action of the user's request
    - NO markdown, quotes, or special punctuation
    - Do NOT start with "Título:" or similar prefixes

    EXAMPLES:
    - User asks to search for patient Juan → "Búsqueda paciente Juan"
    - User asks about hemograma results → "Resultados hemograma"
    - User wants to add glucose exam → "Agregar examen glucosa"
    - User asks what exams are available → "Exámenes disponibles"
    - User sends an image of results → "Pasar datos imagen"

    Args:
        title: Short descriptive title (2-5 words in Spanish)

    Returns:
        Confirmation that title was set
    """
    import httpx

    # Clean up the title
    clean_title = title.strip()
    clean_title = re.sub(r'^\*\*|\*\*$', '', clean_title)  # Remove markdown bold
    clean_title = re.sub(r'^#+\s*', '', clean_title)  # Remove markdown headers
    clean_title = re.sub(r'^["\'"]|["\'"]$', '', clean_title)  # Remove quotes
    clean_title = re.sub(r'^Título:\s*', '', clean_title, flags=re.IGNORECASE)  # Remove "Título:" prefix
    clean_title = re.sub(r'\n.*', '', clean_title)  # Only first line
    clean_title = clean_title.strip()

    # Truncate if too long
    if len(clean_title) > 50:
        clean_title = clean_title[:47] + '...'

    logger.info(f"[Tool] set_chat_title: '{clean_title}'")

    # Directly update the chat title via HTTP call to frontend
    global _current_chat_id
    if _current_chat_id:
        try:
            # Use sync httpx since this is a sync tool
            response = httpx.patch(
                f"http://localhost:3000/api/chats/{_current_chat_id}",
                json={"title": clean_title},
                headers={"X-Internal-Api-Key": "lab-assistant-internal"},
                timeout=5.0
            )
            if response.status_code == 200:
                logger.info(f"[Tool] Chat title updated via API: '{clean_title}'")
            else:
                logger.warning(f"[Tool] Failed to update title via API: {response.status_code}")
        except Exception as e:
            logger.warning(f"[Tool] Error updating title via API: {e}")

    return json.dumps({
        "title": clean_title,
        "status": "title_set"
    }, ensure_ascii=False)


# Function to get all tabs info (used by server.py for context)
async def _get_browser_tabs_impl() -> dict:
    """Get info about all browser tabs."""
    return await _get_all_tabs_info()


# All tools list for binding to model
ALL_TOOLS = [
    search_orders,
    get_order_results,
    get_order_info,
    edit_results,
    edit_order_exams,
    create_new_order,
    ask_user,
    get_available_exams,
    set_chat_title
]

# Tools that should not prevent the response from being final
# These are "passive" tools that are executed but don't require agent to continue
PASSIVE_TOOLS = {'set_chat_title'}
