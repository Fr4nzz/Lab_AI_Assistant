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

logger = logging.getLogger(__name__)

# Global browser instance (will be set during app startup)
_browser: Optional[BrowserManager] = None

# Tab tracking by ID
# Key: order_num (str) for reportes2 tabs, order_id (int) for ordenes/edit tabs
_results_tabs: Dict[str, Any] = {}  # {order_num: Page} - for reportes2
_order_tabs: Dict[int, Any] = {}     # {order_id: Page} - for ordenes/edit


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
    page = await _browser.context.new_page()
    url = f"https://laboratoriofranz.orion-labs.com/reportes2?numeroOrden={order_num}"
    await page.goto(url, timeout=30000)

    try:
        await page.wait_for_load_state('networkidle', timeout=10000)
    except Exception:
        await page.wait_for_timeout(1000)

    await _inject_highlight_styles(page)
    _results_tabs[order_num] = page
    return page


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
    page = await _browser.context.new_page()
    url = f"https://laboratoriofranz.orion-labs.com/ordenes/{order_id}/edit"
    await page.goto(url, timeout=30000)

    try:
        await page.wait_for_load_state('networkidle', timeout=10000)
    except Exception:
        await page.wait_for_timeout(1000)

    _order_tabs[order_id] = page
    return page


async def _get_all_tabs_info() -> dict:
    """Get info about all open browser tabs with IDs and patient names."""
    if not _browser or not _browser.context:
        return {"error": "Browser not available", "tabs": []}

    pages = _browser.context.pages
    tabs_info = []

    for i, page in enumerate(pages):
        url = page.url
        tab_info = {
            "index": i,
            "url": url,
            "type": "unknown",
            "id": None,
            "paciente": None
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

        # Try to extract patient name for relevant tabs
        if tab_info["type"] in ["resultados", "orden_edit", "nueva_orden"]:
            try:
                paciente = await page.evaluate(r"""
                    () => {
                        // Try various selectors for patient name
                        const selectors = ['span.paciente', '.paciente', '[data-paciente]'];
                        for (const sel of selectors) {
                            const el = document.querySelector(sel);
                            if (el) {
                                const text = el.innerText?.trim();
                                if (text && text !== 'Paciente' && text.length > 3) {
                                    return text;
                                }
                            }
                        }
                        return null;
                    }
                """)
                tab_info["paciente"] = paciente
            except Exception:
                pass

        # Mark active tab
        if page == _browser.page:
            tab_info["active"] = True

        tabs_info.append(tab_info)

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
        pages = _browser.context.pages
        if len(pages) > 1:
            await temp_page.close()


async def _get_order_results_impl(order_nums: List[str]) -> dict:
    """
    Get exam result fields for orders. Opens/reuses reportes2 tabs.
    Returns exam fields ready for edit_results().
    """
    import asyncio
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

    results = await asyncio.gather(*[process_order(num) for num in order_nums])

    return {
        "orders": results,
        "total": len(results),
        "tip": "Use edit_results() with order_num to edit these results."
    }


async def _get_order_info_impl(order_ids: List[int]) -> dict:
    """
    Get order info (patient, exams, totals). Opens/reuses ordenes/edit tabs.
    Returns order details ready for edit_order_exams().
    """
    import asyncio
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

    results = await asyncio.gather(*[process_order(oid) for oid in order_ids])

    return {
        "orders": results,
        "total": len(results),
        "tip": "Use edit_order_exams() with order_id to add/remove exams."
    }


async def _edit_results_impl(data: List[Dict[str, str]]) -> dict:
    """Edit exam result fields. Finds tabs by order_num or creates new ones."""
    logger.info(f"[edit_results] Editing {len(data)} fields")

    results = []
    results_by_order = {}

    for item in data:
        order_num = item["orden"]

        # Find or create the tab
        try:
            page = await _find_or_create_results_tab(order_num)
            await page.bring_to_front()

            result = await page.evaluate(FILL_FIELD_JS, {
                "e": item["e"],
                "f": item["f"],
                "v": item["v"]
            })
            result["orden"] = order_num
            results.append(result)
            logger.info(f"[edit_results] {order_num}/{item['f']}: {result}")
        except Exception as e:
            results.append({"orden": order_num, "err": str(e)})

        if order_num not in results_by_order:
            results_by_order[order_num] = {"filled": 0, "errors": 0}
        if "field" in results[-1]:
            results_by_order[order_num]["filled"] += 1
        if "err" in results[-1]:
            results_by_order[order_num]["errors"] += 1

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


async def _edit_order_exams_impl(order_ids: List[int], add: Optional[List[str]] = None, remove: Optional[List[str]] = None) -> dict:
    """Add and/or remove exams from orders by order_id."""
    import asyncio
    add = add or []
    remove = remove or []
    logger.info(f"[edit_order_exams] Editing {len(order_ids)} orders: add={len(add)}, remove={len(remove)}")

    async def process_order(order_id: int) -> dict:
        try:
            page = await _find_or_create_order_tab(order_id)
            await page.bring_to_front()

            added_codes = []
            removed_codes = []
            failed_add = []
            failed_remove = []

            # First, remove exams
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
                                    removed_codes.append(exam_code)
                                    await page.wait_for_timeout(300)
                                else:
                                    failed_remove.append({'codigo': exam_code, 'reason': removed.get('error')})
                            except Exception as e:
                                failed_remove.append({'codigo': exam_code, 'reason': str(e)})
                            break
                    if not found:
                        failed_remove.append({'codigo': exam_code, 'reason': 'not in order'})

            # Then, add exams
            if add:
                for exam_code in add:
                    exam_code_upper = exam_code.upper().strip()
                    search = page.locator('#buscar-examen-input')
                    await search.fill('')
                    await page.wait_for_timeout(200)
                    await search.fill(exam_code_upper)
                    await page.wait_for_timeout(1000)

                    available = await page.evaluate(EXTRACT_AVAILABLE_EXAMS_JS)
                    matched_exam = None
                    for exam in available:
                        if exam.get('codigo') and exam['codigo'].upper() == exam_code_upper:
                            matched_exam = exam
                            break

                    if matched_exam:
                        button_id = matched_exam['button_id']
                        btn = page.locator(f'#{button_id}')
                        if await btn.count() > 0:
                            await btn.click()
                            added_codes.append(exam_code_upper)
                            await page.wait_for_timeout(300)
                        else:
                            failed_add.append({'codigo': exam_code_upper, 'reason': 'button not found'})
                    else:
                        failed_add.append({'codigo': exam_code_upper, 'reason': 'no exact match'})

            # Get updated state
            await page.wait_for_timeout(500)
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

            return {
                "order_id": order_id,
                "added": added_codes,
                "removed": removed_codes,
                "failed_add": failed_add,
                "failed_remove": failed_remove,
                "current_exams": current_exams,
                "totals": totals
            }
        except Exception as e:
            logger.error(f"[edit_order_exams] Error for order {order_id}: {e}")
            return {"order_id": order_id, "error": str(e)}

    results = await asyncio.gather(*[process_order(oid) for oid in order_ids])

    return {
        "orders": results,
        "total": len(results),
        "status": "pending_save",
        "next_step": "Revisa los cambios y haz click en 'Guardar' en cada pestaña."
    }


async def _create_order_impl(cedula: str, exams: List[str]) -> dict:
    """Create a new order with exams."""
    is_cotizacion = not cedula or cedula.strip() == ""
    logger.info(f"[create_order] Creating {'cotización' if is_cotizacion else 'order'} with {len(exams)} exams")

    page = await _browser.ensure_page()
    await page.goto("https://laboratoriofranz.orion-labs.com/ordenes/create")
    await page.wait_for_timeout(1000)

    if not is_cotizacion:
        cedula_input = page.locator('#identificacion')
        await cedula_input.fill(cedula)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)

    added_codes = []
    failed_exams = []

    for exam_code in exams:
        exam_code_upper = exam_code.upper().strip()
        search = page.locator('#buscar-examen-input')
        await search.fill('')
        await page.wait_for_timeout(200)
        await search.fill(exam_code_upper)
        await page.wait_for_timeout(1000)

        available = await page.evaluate(EXTRACT_AVAILABLE_EXAMS_JS)
        matched_exam = None
        for exam in available:
            if exam.get('codigo') and exam['codigo'].upper() == exam_code_upper:
                matched_exam = exam
                break

        if matched_exam:
            button_id = matched_exam['button_id']
            btn = page.locator(f'#{button_id}')
            if await btn.count() > 0:
                await btn.click()
                added_codes.append(exam_code_upper)
                await page.wait_for_timeout(500)
            else:
                failed_exams.append({'codigo': exam_code_upper, 'reason': 'button not found'})
        else:
            failed_exams.append({'codigo': exam_code_upper, 'reason': 'no exact match'})

    await page.wait_for_timeout(500)
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

    return {
        "cedula": cedula if not is_cotizacion else None,
        "is_cotizacion": is_cotizacion,
        "exams_added": [{"codigo": e.get('codigo'), "nombre": e.get('nombre'), "precio": e.get('valor')} for e in added_exams],
        "exams_failed": failed_exams,
        "totals": totals,
        "status": "pending_save",
        "next_step": "Revisa los exámenes y haz click en 'Guardar' para confirmar." if not is_cotizacion else "Esta es solo una cotización."
    }


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
    """
    Search orders by patient name or cedula.

    Args:
        search: Text to search (patient name or cedula). Empty returns recent orders.
        limit: Maximum orders to return (default 20)
        page_num: Page number for pagination
        fecha_desde: Start date filter (YYYY-MM-DD)
        fecha_hasta: End date filter (YYYY-MM-DD)

    Returns:
        JSON with order list. Use 'num' for get_order_results(), 'id' for get_order_info()/edit_order_exams()
    """
    result = await _search_orders_impl(search, limit, page_num, fecha_desde, fecha_hasta)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_order_results(order_nums: List[str]) -> str:
    """
    Get exam result fields for orders (opens /reportes2 tabs).
    Use this before edit_results() to see what fields can be edited.

    BATCH: Pass ALL order numbers at once for efficiency.

    Args:
        order_nums: List of order NUMBERS (e.g., ["2512253", "2512254"])

    Returns:
        JSON with exam fields for each order. Tabs stay open for edit_results().
    """
    result = await _get_order_results_impl(order_nums)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_order_info(order_ids: List[int]) -> str:
    """
    Get order details including exams list (opens /ordenes/edit tabs).
    Use this to see what exams are in an order before editing.

    BATCH: Pass ALL order IDs at once for efficiency.

    Args:
        order_ids: List of order IDs (e.g., [14659, 14660])

    Returns:
        JSON with order details (patient, exams, totals). Tabs stay open for edit_order_exams().
    """
    result = await _get_order_info_impl(order_ids)
    return json.dumps(result, ensure_ascii=False)


class EditResultsInput(BaseModel):
    """Input schema for edit_results."""
    data: List[Dict[str, str]] = Field(
        description="List of edits. Each: orden (order num), e (exam name), f (field name), v (value)"
    )


@tool(args_schema=EditResultsInput)
async def edit_results(data: List[Dict[str, str]]) -> str:
    """
    Edit exam result fields. Finds/creates tabs by order number automatically.
    Fields are auto-highlighted. User must click 'Guardar' to save.

    BATCH: Pass ALL edits for ALL orders at once.

    Args:
        data: List of edits. Each needs: orden, e (exam), f (field), v (value)

    Example:
        edit_results(data=[
            {"orden": "2512253", "e": "BIOMETRIA HEMATICA", "f": "Hemoglobina", "v": "15.5"},
            {"orden": "2512253", "e": "BIOMETRIA HEMATICA", "f": "Hematocrito", "v": "46"}
        ])
    """
    result = await _edit_results_impl(data)
    return json.dumps(result, ensure_ascii=False)


@tool
async def edit_order_exams(order_ids: List[int], add: Optional[List[str]] = None, remove: Optional[List[str]] = None) -> str:
    """
    Add and/or remove exams from orders. Finds/creates tabs by order ID automatically.
    User must click 'Guardar' to save changes.

    BATCH: Pass ALL order IDs at once. Same add/remove applies to all.

    Args:
        order_ids: List of order IDs to modify (e.g., [14659])
        add: Exam codes to add (e.g., ["BH", "EMO"])
        remove: Exam codes to remove (e.g., ["CREA"])

    Examples:
        edit_order_exams(order_ids=[14659], add=["BH", "EMO"])
        edit_order_exams(order_ids=[14659], remove=["CREA"])
        edit_order_exams(order_ids=[14659], add=["BH"], remove=["CREA"])
    """
    result = await _edit_order_exams_impl(order_ids, add, remove)
    return json.dumps(result, ensure_ascii=False)


@tool
async def create_new_order(cedula: str, exams: List[str]) -> str:
    """
    Create new order with exams. Use cedula="" for cotización (price quote).

    Args:
        cedula: Patient cedula. Use "" for cotización only.
        exams: ALL exam codes to add (e.g., ["BH", "EMO", "CREA"])

    Returns:
        JSON with exams added, prices, totals. User must click 'Guardar'.
    """
    result = await _create_order_impl(cedula, exams)
    return json.dumps(result, ensure_ascii=False)


@tool
def ask_user(action: str, message: str) -> str:
    """
    Display a message to the user requesting action or information.

    Args:
        action: Type - "save", "info", "confirm", "clarify"
        message: Message to display
    """
    return json.dumps({
        "waiting_for": action,
        "message": message,
        "status": "waiting_for_user"
    }, ensure_ascii=False)


@tool
async def get_available_exams(order_id: Optional[int] = None) -> str:
    """
    Get list of available exam codes.

    Args:
        order_id: Optional order ID. If provided, also returns currently added exams.

    Returns:
        JSON with available_exams list (codigo, nombre) and added_exams if order_id provided.
    """
    result = await _get_available_exams_impl(order_id)
    return json.dumps(result, ensure_ascii=False)


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
    get_available_exams
]
