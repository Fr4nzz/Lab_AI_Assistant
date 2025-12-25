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
"""
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field
import json
import sys
import logging
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
_active_tabs: Dict[str, Any] = {}  # {orden_num: Page}


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
    """Get the active tabs dictionary."""
    return _active_tabs


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


def close_tab(orden: str):
    """Close a specific tab."""
    global _active_tabs
    if orden in _active_tabs:
        # Note: This needs to be called from async context
        pass
    if orden in _active_tabs:
        del _active_tabs[orden]


def close_all_tabs():
    """Close all active tabs."""
    global _active_tabs
    _active_tabs.clear()


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
    """Internal async implementation of search_orders - supports parallel execution."""
    from urllib.parse import urlencode, quote

    logger.info(f"[search_orders] Searching: '{search}', page={page_num}, desde={fecha_desde}, hasta={fecha_hasta}")

    # Build URL with query parameters
    params = {"page": page_num}
    if search:
        params["cadenaBusqueda"] = search
    if fecha_desde:
        params["fechaDesde"] = fecha_desde
    if fecha_hasta:
        params["fechaHasta"] = fecha_hasta

    url = f"https://laboratoriofranz.orion-labs.com/ordenes?{urlencode(params)}"

    # Use a NEW page for each search to support parallel execution
    # This prevents ERR_ABORTED when multiple searches run simultaneously
    temp_page = await _browser.context.new_page()

    try:
        await temp_page.goto(url, timeout=30000)

        # Wait for content to load
        try:
            await temp_page.wait_for_load_state('networkidle', timeout=10000)
        except Exception:
            try:
                await temp_page.wait_for_selector('table tbody tr', timeout=5000)
            except Exception:
                await temp_page.wait_for_timeout(1000)

        ordenes = await temp_page.evaluate(EXTRACT_ORDENES_JS)
        logger.info(f"[search_orders] Found {len(ordenes)} orders")

        return {
            "ordenes": ordenes[:limit],
            "total": len(ordenes[:limit]),
            "page": page_num,
            "filters": {
                "search": search or None,
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta
            },
            "tip": "Use 'num' field for get_exam_fields(), use 'id' field for get_order_details()"
        }
    finally:
        # Close the temp page to avoid too many open tabs
        # But keep at least one page in the browser
        pages = _browser.context.pages
        if len(pages) > 1:
            await temp_page.close()


async def _get_exam_fields_impl(ordenes: List[str]) -> dict:
    """Internal async implementation of get_exam_fields - PARALLELIZED."""
    global _active_tabs
    import asyncio
    logger.info(f"[get_exam_fields] Getting fields for {len(ordenes)} orders in parallel...")

    async def process_order(orden: str) -> dict:
        """Process a single order - runs in parallel with others."""
        try:
            # Reuse existing tab or create new one
            if orden in _active_tabs:
                page = _active_tabs[orden]
                try:
                    await page.reload()
                except Exception:
                    page = await _browser.context.new_page()
                    _active_tabs[orden] = page
            else:
                page = await _browser.context.new_page()
                _active_tabs[orden] = page

            url = f"https://laboratoriofranz.orion-labs.com/reportes2?numeroOrden={orden}"
            await page.goto(url, timeout=30000)

            # Wait for page to be ready using Playwright's load state instead of fixed timeout
            try:
                # 'networkidle' waits until no network connections for 500ms
                await page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                # Fallback: wait for content to appear
                try:
                    await page.wait_for_selector('.parametro, .card, table tbody tr', timeout=5000)
                except Exception:
                    # Last resort: minimal wait
                    await page.wait_for_timeout(500)

            # Inject highlight styles
            await _inject_highlight_styles(page)

            data = await page.evaluate(EXTRACT_REPORTES_JS)
            exam_count = len(data.get('examenes', []))
            logger.info(f"[get_exam_fields] Order {orden}: {exam_count} exams")

            return {
                "orden": orden,
                "tab_ready": True,
                **data
            }
        except Exception as e:
            logger.error(f"[get_exam_fields] Error processing order {orden}: {e}")
            return {
                "orden": orden,
                "tab_ready": False,
                "error": str(e)
            }

    # Process all orders in parallel
    results = await asyncio.gather(*[process_order(orden) for orden in ordenes])

    return {
        "ordenes": results,
        "total": len(results),
        "tabs_open": len(_active_tabs),
        "tip": "Tabs are ready. Use edit_results() with ALL fields you want to change."
    }


async def _get_order_details_impl(order_ids: List[int]) -> dict:
    """Internal async implementation of get_order_details - PARALLELIZED."""
    import asyncio
    logger.info(f"[get_order_details] Getting details for {len(order_ids)} orders in parallel...")

    async def process_order(order_id: int) -> dict:
        """Process a single order - runs in parallel with others."""
        try:
            page = await _browser.context.new_page()
            url = f"https://laboratoriofranz.orion-labs.com/ordenes/{order_id}/edit"
            await page.goto(url, timeout=30000)

            # Wait for page to be ready
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                try:
                    await page.wait_for_selector('form, .card, input', timeout=5000)
                except Exception:
                    await page.wait_for_timeout(500)

            data = await page.evaluate(EXTRACT_ORDEN_EDIT_JS)
            data["order_id"] = order_id
            await page.close()  # Close temp page
            return data
        except Exception as e:
            logger.error(f"[get_order_details] Error processing order {order_id}: {e}")
            return {"order_id": order_id, "error": str(e)}

    # Process all orders in parallel
    results = await asyncio.gather(*[process_order(order_id) for order_id in order_ids])

    return {
        "orders": results,
        "total": len(results)
    }


async def _edit_results_impl(data: List[Dict[str, str]]) -> dict:
    """Internal async implementation of edit_results."""
    global _active_tabs
    logger.info(f"[edit_results] Editing {len(data)} fields")

    results = []
    results_by_orden = {}

    for item in data:
        orden = item["orden"]

        if orden not in _active_tabs:
            results.append({
                "orden": orden,
                "err": f"No tab open for order {orden}. Call get_exam_fields first."
            })
            continue

        page = _active_tabs[orden]

        try:
            await page.bring_to_front()

            result = await page.evaluate(FILL_FIELD_JS, {
                "e": item["e"],
                "f": item["f"],
                "v": item["v"]
            })
            result["orden"] = orden
            results.append(result)
            logger.info(f"[edit_results] {orden}/{item['f']}: {result}")
        except Exception as e:
            results.append({
                "orden": orden,
                "err": str(e)
            })

        if orden not in results_by_orden:
            results_by_orden[orden] = {"filled": 0, "errors": 0}
        if "field" in results[-1]:
            results_by_orden[orden]["filled"] += 1
        if "err" in results[-1]:
            results_by_orden[orden]["errors"] += 1

    filled = len([r for r in results if "field" in r])
    errors = [r for r in results if "err" in r]

    return {
        "filled": filled,
        "total": len(data),
        "by_orden": results_by_orden,
        "details": results,
        "errors": errors,
        "next_step": "Ask user to review highlighted fields and click 'Guardar' in each tab."
    }


async def _add_exam_impl(order_id: int, exam_code: str) -> dict:
    """Internal async implementation of add_exam_to_order."""
    exam_code_upper = exam_code.upper().strip()
    logger.info(f"[add_exam] Adding {exam_code_upper} to order {order_id}")

    page = await _browser.ensure_page()
    url = f"https://laboratoriofranz.orion-labs.com/ordenes/{order_id}/edit"
    await page.goto(url)
    await page.wait_for_timeout(1500)

    # Clear and search for the exam
    search = page.locator('#buscar-examen-input')
    await search.fill('')
    await page.wait_for_timeout(200)
    await search.fill(exam_code_upper)
    await page.wait_for_timeout(1000)  # Wait for search results

    # Extract available exams after search to find exact match
    available = await page.evaluate(EXTRACT_AVAILABLE_EXAMS_JS)

    # Find exact match by code
    matched_exam = None
    for exam in available:
        if exam.get('codigo') and exam['codigo'].upper() == exam_code_upper:
            matched_exam = exam
            break

    if matched_exam:
        # Click the specific button for this exam
        button_id = matched_exam['button_id']
        btn = page.locator(f'#{button_id}')
        if await btn.count() > 0:
            await btn.click()
            logger.info(f"[add_exam] Added: {matched_exam['codigo']} - {matched_exam['nombre']}")
            return {
                "added": {
                    "codigo": matched_exam['codigo'],
                    "nombre": matched_exam['nombre']
                },
                "order_id": order_id,
                "status": "pending_save"
            }

    return {"error": f"Could not find exam with code '{exam_code_upper}'", "order_id": order_id}


async def _create_order_impl(cedula: str, exams: List[str]) -> dict:
    """Internal async implementation of create_new_order."""
    # For cotización, skip cedula to avoid patient creation popup
    is_cotizacion = not cedula or cedula == "0000000000" or cedula.strip() == ""
    logger.info(f"[create_order] Creating order for {'cotización' if is_cotizacion else cedula} with exams: {exams}")

    page = await _browser.ensure_page()
    await page.goto("https://laboratoriofranz.orion-labs.com/ordenes/create")
    await page.wait_for_timeout(1000)

    # Only fill cedula if it's a real patient ID (not cotización)
    if not is_cotizacion:
        cedula_input = page.locator('#identificacion')
        await cedula_input.fill(cedula)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)

    added_codes = []  # Track codes we successfully clicked
    failed_exams = []

    for exam_code in exams:
        exam_code_upper = exam_code.upper().strip()

        # Clear and search for the exam
        search = page.locator('#buscar-examen-input')
        await search.fill('')
        await page.wait_for_timeout(200)
        await search.fill(exam_code_upper)
        await page.wait_for_timeout(1000)  # Wait for search results

        # Extract available exams after search to find exact match
        available = await page.evaluate(EXTRACT_AVAILABLE_EXAMS_JS)

        # Find exact match by code
        matched_exam = None
        for exam in available:
            if exam.get('codigo') and exam['codigo'].upper() == exam_code_upper:
                matched_exam = exam
                break

        if matched_exam:
            # Click the specific button for this exam
            button_id = matched_exam['button_id']
            btn = page.locator(f'#{button_id}')
            if await btn.count() > 0:
                await btn.click()
                added_codes.append(exam_code_upper)
                logger.info(f"[create_order] Added exam: {matched_exam['codigo']} - {matched_exam['nombre']}")
                await page.wait_for_timeout(500)
            else:
                failed_exams.append({'codigo': exam_code_upper, 'reason': 'button not found'})
                logger.warning(f"[create_order] Button {button_id} not found for {exam_code_upper}")
        else:
            failed_exams.append({'codigo': exam_code_upper, 'reason': 'no exact match found'})
            logger.warning(f"[create_order] No exact match for exam code: {exam_code_upper}")

    # Wait a bit for the table to update, then extract added exams with individual prices
    await page.wait_for_timeout(500)
    added_exams_with_prices = await page.evaluate(EXTRACT_ADDED_EXAMS_JS)

    # Build list of added exams with prices
    added_exams = []
    for exam in added_exams_with_prices:
        added_exams.append({
            'codigo': exam.get('codigo'),
            'nombre': exam.get('nombre'),
            'precio': exam.get('valor')  # Individual price for this exam
        })
        logger.info(f"[create_order] Exam price: {exam.get('codigo')} = {exam.get('valor')}")

    # Extract totals from the order form
    totals = await page.evaluate(r"""
        () => {
            const result = { subtotal: null, descuento: null, total: null };

            // Get descuento from input
            const descuentoInput = document.querySelector('#valor-descuento');
            if (descuentoInput) result.descuento = descuentoInput.value;

            // Get total from bold price element (usually shows total like $XX.XX)
            document.querySelectorAll('.fw-bold, .fs-5, .text-end').forEach(el => {
                const text = el.innerText?.trim() || '';
                if (text.startsWith('$') && !result.total) {
                    result.total = text;
                }
            });

            // Also try to get from examenes-seleccionados totals row
            const totalRow = document.querySelector('#examenes-seleccionados tfoot, .total-row');
            if (totalRow) {
                const totalText = totalRow.innerText?.match(/\$[\d.]+/);
                if (totalText) result.total = totalText[0];
            }

            return result;
        }
    """)

    # Build result message based on mode
    if is_cotizacion:
        message = f"Cotización: {len(added_exams)} exámenes. Total: {totals.get('total', 'N/A')}"
        next_step = "Esta es solo una cotización. Cierra la pestaña sin guardar, o ingresa cédula del paciente para crear la orden."
    else:
        message = f"Orden creada con {len(added_exams)} examenes. Total: {totals.get('total', 'N/A')}"
        next_step = "Revisa los examenes en el navegador. Haz click en 'Guardar' para confirmar o cierra la pestaña para cancelar."

    result = {
        "cedula": cedula if not is_cotizacion else None,
        "is_cotizacion": is_cotizacion,
        "exams_added": added_exams,  # Now includes individual prices
        "exams_failed": failed_exams,
        "totals": totals,
        "status": "pending_review",
        "message": message,
        "next_step": next_step
    }

    if failed_exams:
        result["warning"] = f"Some exams could not be added: {[e['codigo'] for e in failed_exams]}"

    logger.info(f"[create_order] Created order with total: {totals.get('total', 'N/A')}")
    return result


async def _highlight_impl(fields: List[str], color: str = "yellow") -> dict:
    """Internal async implementation of highlight_fields."""
    color_map = {
        "yellow": "#fef3c7",
        "green": "#d1fae5",
        "red": "#fee2e2",
        "blue": "#dbeafe"
    }

    highlighted = []
    for orden, page in _active_tabs.items():
        try:
            await page.evaluate("""
                (params) => {
                    const rows = document.querySelectorAll('tr.parametro');
                    for (const row of rows) {
                        const label = row.querySelector('td:first-child')?.innerText?.trim();
                        for (const field of params.fields) {
                            if (label && label.toLowerCase().includes(field.toLowerCase())) {
                                row.style.backgroundColor = params.color;
                            }
                        }
                    }
                }
            """, {"fields": fields, "color": color_map.get(color, "#fef3c7")})
            highlighted.append(orden)
        except Exception:
            pass

    return {
        "highlighted_fields": fields,
        "in_tabs": highlighted,
        "color": color
    }


async def _get_available_exams_impl(order_id: Optional[int] = None) -> dict:
    """
    Internal async implementation of get_available_exams.
    Gets list of available exams from create or edit order page.
    """
    logger.info(f"[get_available_exams] Getting available exams, order_id={order_id}")
    page = await _browser.ensure_page()

    # Navigate to create or edit page based on order_id
    if order_id:
        url = f"https://laboratoriofranz.orion-labs.com/ordenes/{order_id}/edit"
    else:
        url = "https://laboratoriofranz.orion-labs.com/ordenes/create"

    await page.goto(url, timeout=30000)
    await page.wait_for_timeout(1500)

    # Extract available exams
    available = await page.evaluate(EXTRACT_AVAILABLE_EXAMS_JS)

    # Also extract currently added exams if on edit page
    added = []
    if order_id:
        added = await page.evaluate(EXTRACT_ADDED_EXAMS_JS)

    logger.info(f"[get_available_exams] Found {len(available)} available, {len(added)} added")

    return {
        "order_id": order_id,
        "available_exams": available,
        "total_available": len(available),
        "added_exams": added if order_id else [],
        "total_added": len(added) if order_id else 0,
        "tip": "Use exam 'codigo' field with add_exam_to_order() to add exams"
    }


async def _get_browser_tabs_impl() -> dict:
    """
    Internal async implementation of get_browser_tabs.
    Gets info about all open browser tabs, with detailed state for the active tab.
    """
    logger.info("[get_browser_tabs] Getting browser tabs info...")

    tabs_info = []
    active_tab_index = None
    active_tab_state = None

    # Get all pages from browser context
    if not _browser or not _browser.context:
        return {"error": "Browser not available", "tabs": []}

    pages = _browser.context.pages

    for i, page in enumerate(pages):
        url = page.url

        # Determine tab type based on URL
        tab_type = "unknown"
        if '/ordenes/create' in url:
            tab_type = "nueva_orden"
        elif '/ordenes/' in url and '/edit' in url:
            tab_type = "orden_edit"
        elif '/ordenes' in url and '/ordenes/' not in url:
            tab_type = "ordenes_list"
        elif '/reportes2' in url:
            tab_type = "resultados"
        elif '/login' in url:
            tab_type = "login"

        tab_info = {
            "index": i,
            "url": url,
            "type": tab_type
        }

        # Check if this is the active (front) tab
        # The main page from browser manager is typically the active one
        if page == _browser.page:
            active_tab_index = i
            tab_info["active"] = True

        tabs_info.append(tab_info)

    # Get detailed state for the active tab
    if active_tab_index is not None and active_tab_index < len(pages):
        active_page = pages[active_tab_index]
        extractor = PageDataExtractor(active_page)
        try:
            active_tab_state = await extractor.extract_current_page()

            # For orden_create, also get added exams with prices
            if active_tab_state.get("page_type") == "orden_create":
                added_exams = await active_page.evaluate(EXTRACT_ADDED_EXAMS_JS)
                active_tab_state["examenes_agregados"] = added_exams

                # Also get totals
                totals = await active_page.evaluate(r"""
                    () => {
                        const result = { subtotal: null, descuento: null, total: null };
                        const descuentoInput = document.querySelector('#valor-descuento');
                        if (descuentoInput) result.descuento = descuentoInput.value;
                        document.querySelectorAll('.fw-bold, .fs-5, .text-end').forEach(el => {
                            const text = el.innerText?.trim() || '';
                            if (text.startsWith('$') && !result.total) {
                                result.total = text;
                            }
                        });
                        return result;
                    }
                """)
                active_tab_state["totales"] = totals

        except Exception as e:
            logger.warning(f"[get_browser_tabs] Could not extract active tab state: {e}")
            active_tab_state = {"error": str(e)}

    logger.info(f"[get_browser_tabs] Found {len(tabs_info)} tabs, active: {active_tab_index}")

    return {
        "tabs": tabs_info,
        "total": len(tabs_info),
        "active_tab_index": active_tab_index,
        "active_tab_state": active_tab_state
    }


async def _add_exam_to_current_tab_impl(exams: List[str]) -> dict:
    """
    Internal async implementation of add_exam_to_current_tab.
    Adds exams to an already open nueva_orden or orden_edit tab.
    """
    logger.info(f"[add_exam_to_current_tab] Adding {len(exams)} exams to current tab...")

    # Get current page
    page = await _browser.ensure_page()
    url = page.url

    # Verify we're on a create or edit order page
    if '/ordenes/create' not in url and '/edit' not in url:
        return {
            "error": f"Current tab is not an order page. URL: {url}",
            "tip": "Navigate to /ordenes/create or /ordenes/ID/edit first"
        }

    added_codes = []
    failed_exams = []

    for exam_code in exams:
        exam_code_upper = exam_code.upper().strip()

        # Clear and search for the exam
        search = page.locator('#buscar-examen-input')
        await search.fill('')
        await page.wait_for_timeout(200)
        await search.fill(exam_code_upper)
        await page.wait_for_timeout(1000)  # Wait for search results

        # Extract available exams after search to find exact match
        available = await page.evaluate(EXTRACT_AVAILABLE_EXAMS_JS)

        # Find exact match by code
        matched_exam = None
        for exam in available:
            if exam.get('codigo') and exam['codigo'].upper() == exam_code_upper:
                matched_exam = exam
                break

        if matched_exam:
            # Click the specific button for this exam
            button_id = matched_exam['button_id']
            btn = page.locator(f'#{button_id}')
            if await btn.count() > 0:
                await btn.click()
                added_codes.append(exam_code_upper)
                logger.info(f"[add_exam_to_current_tab] Added exam: {matched_exam['codigo']} - {matched_exam['nombre']}")
                await page.wait_for_timeout(500)
            else:
                failed_exams.append({'codigo': exam_code_upper, 'reason': 'button not found'})
        else:
            failed_exams.append({'codigo': exam_code_upper, 'reason': 'no exact match found'})
            logger.warning(f"[add_exam_to_current_tab] No exact match for exam code: {exam_code_upper}")

    # Get updated exam list and totals
    await page.wait_for_timeout(500)
    added_exams_with_prices = await page.evaluate(EXTRACT_ADDED_EXAMS_JS)

    totals = await page.evaluate(r"""
        () => {
            const result = { subtotal: null, descuento: null, total: null };
            const descuentoInput = document.querySelector('#valor-descuento');
            if (descuentoInput) result.descuento = descuentoInput.value;
            document.querySelectorAll('.fw-bold, .fs-5, .text-end').forEach(el => {
                const text = el.innerText?.trim() || '';
                if (text.startsWith('$') && !result.total) {
                    result.total = text;
                }
            });
            return result;
        }
    """)

    result = {
        "added": added_codes,
        "failed": failed_exams,
        "current_exams": added_exams_with_prices,
        "totals": totals,
        "status": "pending_save",
        "next_step": "Revisa los examenes en el navegador. Haz click en 'Guardar' para confirmar."
    }

    if failed_exams:
        result["warning"] = f"Some exams could not be added: {[e['codigo'] for e in failed_exams]}"

    logger.info(f"[add_exam_to_current_tab] Added {len(added_codes)} exams, total: {totals.get('total', 'N/A')}")
    return result


# ============================================================
# TOOL DEFINITIONS (Sync wrappers that LangGraph can call)
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
    Search orders by patient name or ID number (cedula).
    Returns a list of matching orders with their IDs for further operations.
    Supports pagination and date filters.

    Args:
        search: Text to search (patient name or cedula). Empty returns recent orders.
        limit: Maximum orders to return (default 20)
        page_num: Page number for pagination (default 1)
        fecha_desde: Start date filter in format YYYY-MM-DD (optional)
        fecha_hasta: End date filter in format YYYY-MM-DD (optional)

    Returns:
        JSON with order list including: num, fecha, paciente, cedula, estado, id

    Example:
        search_orders(search="chandi franz", limit=10)
        search_orders(page_num=2)  # Get second page
        search_orders(fecha_desde="2025-01-01", fecha_hasta="2025-01-31")  # Filter by date range
    """
    result = await _search_orders_impl(search, limit, page_num, fecha_desde, fecha_hasta)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_exam_fields(ordenes: List[str]) -> str:
    """
    Get exam fields for ONE OR MORE orders. Opens browser tabs for editing.
    BATCH OPERATION: Pass ALL order numbers you need at once to minimize iterations.

    Args:
        ordenes: List of order NUMBERS (the 'num' field, e.g., ["2501181", "25011314"])

    Returns:
        JSON with exam fields for each order, tabs remain open for edit_results()

    Example - Single order:
        get_exam_fields(ordenes=["2501181"])

    Example - Multiple orders (PREFERRED for efficiency):
        get_exam_fields(ordenes=["2501181", "25011314", "2501200"])
    """
    result = await _get_exam_fields_impl(ordenes)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_order_details(order_ids: List[int]) -> str:
    """
    Get details of ONE OR MORE orders by their internal IDs.
    Use this to check what exams exist in orders before editing.
    BATCH OPERATION: Pass ALL order IDs you need at once.

    Args:
        order_ids: List of internal order IDs (the 'id' field, e.g., [4282, 4150])

    Returns:
        JSON with order details (patient info, exams list, totals) for each order
    """
    result = await _get_order_details_impl(order_ids)
    return json.dumps(result, ensure_ascii=False)


class EditResultsInput(BaseModel):
    """Input schema for edit_results tool."""
    data: List[Dict[str, str]] = Field(
        description="List of field edits. Each item must have: orden (order number), e (exam name), f (field name), v (value)"
    )


@tool(args_schema=EditResultsInput)
async def edit_results(data: List[Dict[str, str]]) -> str:
    """
    Edit exam result fields in browser forms. Fields are auto-highlighted.
    BATCH OPERATION: Pass ALL fields for ALL orders at once.

    IMPORTANT: This only FILLS the forms. User must click "Guardar" to save.

    Args:
        data: List of edits. Each item needs:
            - orden: Order NUMBER (e.g., "2501181")
            - e: Exam name (e.g., "BIOMETRIA HEMATICA")
            - f: Field name (e.g., "Hemoglobina")
            - v: Value to set (e.g., "15.5")

    Returns:
        Summary of fields filled, with before/after values
    """
    result = await _edit_results_impl(data)
    return json.dumps(result, ensure_ascii=False)


@tool
async def add_exam_to_order(order_id: int, exam_code: str) -> str:
    """
    Add an exam to an existing order. Form must be saved manually by user.

    Args:
        order_id: Internal order ID (the 'id' field)
        exam_code: Exam code to add (e.g., "EMO", "BH", "COPROPARASITARIO")

    Returns:
        Confirmation message. User must click Guardar to save.
    """
    result = await _add_exam_impl(order_id, exam_code)
    return json.dumps({
        **result,
        "next_step": "User must click 'Guardar' to save the exam to the order."
    }, ensure_ascii=False)


@tool
async def create_new_order(cedula: str, exams: List[str]) -> str:
    """
    Create a new order form with multiple exams. Use for cotización (price quotes).

    For cotización: use cedula="" (empty) and pass ALL exam codes at once.
    The tool returns individual prices and total, leaves browser open for review.

    Args:
        cedula: Patient ID number (cedula). Use "" (empty string) for cotización only.
        exams: List of ALL exam codes to add at once (e.g., ["BH", "GLU", "AMI", "LIPA", "WIDAL"])

    Returns:
        JSON with exams added (with individual prices), totals, and status.

    Example for cotización:
        create_new_order(cedula="", exams=["BH", "AMI", "LIPA", "WIDAL", "PCR"])

    Example for real order:
        create_new_order(cedula="1234567890", exams=["BH", "EMO"])
    """
    result = await _create_order_impl(cedula, exams)
    return json.dumps(result, ensure_ascii=False)


@tool
async def highlight_fields(fields: List[str], color: str = "yellow") -> str:
    """
    Highlight specific fields in the browser to draw user attention.

    Args:
        fields: Field names to highlight (partial match)
        color: Highlight color - yellow, green, red, or blue
    """
    result = await _highlight_impl(fields, color)
    return json.dumps(result, ensure_ascii=False)


@tool
def ask_user(action: str, message: str) -> str:
    """
    Display a message to the user requesting action or information.

    Args:
        action: Type of request - "save", "info", "confirm", "clarify"
        message: Message to display to the user
    """
    return json.dumps({
        "waiting_for": action,
        "message": message,
        "status": "waiting_for_user"
    }, ensure_ascii=False)


@tool
async def get_available_exams(order_id: Optional[int] = None) -> str:
    """
    Get list of available exams that can be added to orders.
    Also returns currently added exams if editing an existing order.

    Use this tool:
    - Before creating a new order to see what exams are available
    - When user wants to add exams but you don't know the exact codes
    - To check what exams are already added to an order

    Args:
        order_id: Optional internal order ID. If provided, navigates to edit page
                  and also returns currently added exams.
                  If not provided, navigates to create new order page.

    Returns:
        JSON with available_exams (list with codigo, nombre) and added_exams if editing.

    Example - For new order:
        get_available_exams()

    Example - For existing order:
        get_available_exams(order_id=4282)
    """
    result = await _get_available_exams_impl(order_id)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_browser_tabs() -> str:
    """
    Get info about all open browser tabs and detailed state of the active tab.

    Use this tool to:
    - See what tabs are currently open (ordenes_list, resultados, nueva_orden, orden_edit)
    - Get the current state of the active tab (exams already added, totals, etc.)
    - Decide whether to continue working on an existing tab or open a new one

    Returns:
        JSON with:
        - tabs: List of all tabs with URL and type
        - active_tab_index: Index of the active (front) tab
        - active_tab_state: Detailed state of active tab based on its type

    Tab types:
        - ordenes_list: Main orders list page
        - nueva_orden: New order creation page
        - orden_edit: Editing existing order
        - resultados: Entering exam results
        - login: Login page
    """
    result = await _get_browser_tabs_impl()
    return json.dumps(result, ensure_ascii=False)


@tool
async def add_exam_to_current_tab(exams: List[str]) -> str:
    """
    Add exams to the currently open order tab (nueva_orden or orden_edit).

    Use this tool when:
    - A previous create_new_order had some exams fail and you want to add them
    - You're on an order page and need to add more exams without starting over
    - The active tab is already on /ordenes/create or /ordenes/ID/edit

    IMPORTANT: This does NOT navigate away from the current tab. It adds exams
    to whatever order form is currently open.

    Args:
        exams: List of exam codes to add (e.g., ["PCRSCNT", "CREA", "GLU"])

    Returns:
        JSON with added exams, failed exams, current totals, and next steps.

    Example:
        add_exam_to_current_tab(exams=["PCRSCNT", "BH"])
    """
    result = await _add_exam_to_current_tab_impl(exams)
    return json.dumps(result, ensure_ascii=False)


# All tools list for binding to model
ALL_TOOLS = [
    search_orders,
    get_exam_fields,
    get_order_details,
    edit_results,
    add_exam_to_order,
    create_new_order,
    highlight_fields,
    ask_user,
    get_available_exams,
    get_browser_tabs,
    add_exam_to_current_tab
]
