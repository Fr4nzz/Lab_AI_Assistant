"""
Tool Executor - Executes AI tool calls with tab reuse and auto-highlight.
"""
from typing import Dict, Optional
from playwright.async_api import Page, BrowserContext

from .browser_manager import BrowserManager
from .extractors import PageDataExtractor, EXTRACT_REPORTES_JS, EXTRACT_ORDEN_EDIT_JS


# CSS para resaltar campos modificados
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


# JavaScript para llenar un campo y auto-resaltarlo
FILL_FIELD_JS = r"""
(params) => {
    const rows = document.querySelectorAll('tr.parametro');

    for (const row of rows) {
        const labelCell = row.querySelector('td:first-child');
        const labelText = labelCell?.innerText?.trim();

        // Buscar por nombre de campo (puede ser parcial)
        if (!labelText || !labelText.toLowerCase().includes(params.f.toLowerCase())) {
            continue;
        }

        const input = row.querySelector('input');
        const select = row.querySelector('select');
        const control = input || select;

        if (!control) continue;

        // Guardar valor anterior
        const prev = input ? input.value : (select.options[select.selectedIndex]?.text || '');

        // Llenar el campo
        if (input) {
            input.value = params.v;
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
        } else if (select) {
            // Buscar opción que coincida (parcial, case-insensitive)
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
                return {err: 'Option not found: ' + params.v + ' for field ' + params.f};
            }
        }

        // AUTO-HIGHLIGHT
        control.classList.add('ai-modified');
        row.classList.add('ai-modified-row');

        // Agregar badge de cambio
        const existingBadge = control.parentNode.querySelector('.ai-change-badge');
        if (!existingBadge) {
            const indicator = document.createElement('span');
            indicator.className = 'ai-change-badge';
            indicator.textContent = prev + ' → ' + params.v;
            control.parentNode.appendChild(indicator);
        }

        // Scroll al campo
        control.scrollIntoView({behavior: 'smooth', block: 'center'});

        return {field: labelText, prev: prev, new: params.v};
    }

    return {err: 'Field not found: ' + params.f};
}
"""


class ToolExecutor:
    """Ejecuta las llamadas a herramientas del AI con reutilización de pestañas y auto-resaltado."""

    def __init__(self, browser_manager: BrowserManager):
        self.browser = browser_manager
        self.active_tabs: Dict[str, Page] = {}  # {orden_num: Page} - pestañas reusables
        self.bg_context: Optional[BrowserContext] = None

    async def init_background_context(self):
        """Inicializa contexto de navegador oculto para operaciones en segundo plano."""
        if not self.bg_context and self.browser.playwright:
            self.bg_context = await self.browser.playwright.chromium.launch_persistent_context(
                user_data_dir=self.browser.user_data_dir,
                headless=True,
                channel="msedge"
            )

    async def execute(self, tool_name: str, params: dict) -> dict:
        """Ejecuta una herramienta y retorna el resultado."""
        method = getattr(self, f"_exec_{tool_name}", None)
        if not method:
            return {"ok": False, "err": f"Unknown tool: {tool_name}"}

        try:
            result = await method(params)
            return {"ok": True, **result}
        except Exception as e:
            return {"ok": False, "err": str(e)}

    # ============================================================
    # BACKGROUND TOOLS
    # ============================================================

    async def _exec_get_reportes(self, p: dict) -> dict:
        """Obtiene datos de reportes Y mantiene la pestaña abierta para editar."""
        orden = p["orden"]

        # Verificar si ya existe una pestaña para esta orden
        if orden in self.active_tabs:
            page = self.active_tabs[orden]
            await page.reload()
        else:
            # Crear nueva pestaña
            page = await self.browser.context.new_page()
            self.active_tabs[orden] = page

        url = f"https://laboratoriofranz.orion-labs.com/reportes2?numeroOrden={orden}"
        await page.goto(url, timeout=30000)
        await page.wait_for_timeout(2000)  # Esperar Vue.js

        # Inyectar estilos de resaltado preventivamente
        await self._inject_highlight_styles(page)

        # Extraer datos
        data = await page.evaluate(EXTRACT_REPORTES_JS)

        return {"orden": orden, "tab_ready": True, **data}

    async def _exec_get_orden(self, p: dict) -> dict:
        """Obtiene detalles de una orden - en segundo plano."""
        await self.init_background_context()
        page = await self._get_bg_page()

        url = f"https://laboratoriofranz.orion-labs.com/ordenes/{p['id']}/edit"
        await page.goto(url, timeout=30000)
        await page.wait_for_timeout(1500)

        return await page.evaluate(EXTRACT_ORDEN_EDIT_JS)

    # ============================================================
    # ORDER MANAGEMENT TOOLS (Visible)
    # ============================================================

    async def _exec_create_orden(self, p: dict) -> dict:
        """Crea una nueva orden con paciente y exámenes."""
        page = self.browser.page

        await page.goto("https://laboratoriofranz.orion-labs.com/ordenes/create")
        await page.wait_for_timeout(1000)

        # Llenar cédula
        cedula_input = page.locator('#identificacion')
        await cedula_input.fill(p["cedula"])
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)  # Esperar carga de datos del paciente

        # Agregar cada examen
        for exam in p.get("exams", []):
            search = page.locator('#buscar-examen-input')
            await search.fill(exam)
            await page.wait_for_timeout(800)

            # Buscar botón de agregar
            add_btn = page.locator('button[id*="examen"]').first
            if await add_btn.count() > 0:
                await add_btn.click()
                await page.wait_for_timeout(500)

        return {"created": True, "cedula": p["cedula"], "exams": p.get("exams", [])}

    async def _exec_add_exam(self, p: dict) -> dict:
        """Agrega un examen a una orden existente."""
        page = self.browser.page

        url = f"https://laboratoriofranz.orion-labs.com/ordenes/{p['id']}/edit"
        await page.goto(url)
        await page.wait_for_timeout(1500)

        # Buscar y agregar examen
        search = page.locator('#buscar-examen-input')
        await search.fill(p["exam"])
        await page.wait_for_timeout(800)

        add_btn = page.locator('button[id*="examen"]').first
        if await add_btn.count() > 0:
            await add_btn.click()

        return {"added": p["exam"], "order_id": p["id"]}

    # ============================================================
    # RESULT EDITING TOOLS (Visible, Auto-Highlight)
    # ============================================================

    async def _exec_fill(self, p: dict) -> dict:
        """Llena un campo con auto-resaltado."""
        page = self._get_active_page()

        # Hacer la pestaña visible
        await page.bring_to_front()

        # Llenar y resaltar
        result = await page.evaluate(FILL_FIELD_JS, {"e": p["e"], "f": p["f"], "v": p["v"]})

        return result

    async def _exec_fill_many(self, p: dict) -> dict:
        """Llena múltiples campos con auto-resaltado."""
        results = []
        first_scroll = True

        for item in p["data"]:
            r = await self._exec_fill(item)
            results.append(r)

            # Solo hacer scroll al primer campo modificado
            if first_scroll and "field" in r:
                first_scroll = False

        filled = len([r for r in results if "field" in r])
        errors = [r for r in results if "err" in r]

        return {
            "filled": filled,
            "total": len(p["data"]),
            "details": results,
            "errors": errors
        }

    # ============================================================
    # UI TOOLS
    # ============================================================

    async def _exec_hl(self, p: dict) -> dict:
        """Resalta campos específicos (sin editarlos)."""
        page = self._get_active_page()

        color_map = {
            "yellow": "#fef3c7",
            "green": "#d1fae5",
            "red": "#fee2e2",
            "blue": "#dbeafe"
        }
        color = color_map.get(p.get("color", "yellow"), "#fef3c7")

        await page.evaluate("""
            (params) => {
                const rows = document.querySelectorAll('tr.parametro');
                let found = [];

                for (const row of rows) {
                    const label = row.querySelector('td:first-child')?.innerText?.trim();

                    for (const field of params.fields) {
                        if (label && label.toLowerCase().includes(field.toLowerCase())) {
                            row.style.backgroundColor = params.color;
                            row.scrollIntoView({behavior: 'smooth', block: 'center'});
                            found.push(label);
                        }
                    }
                }

                return found;
            }
        """, {"fields": p["fields"], "color": color})

        return {"highlighted": p["fields"]}

    async def _exec_ask_user(self, p: dict) -> dict:
        """Solicita una acción del usuario."""
        return {
            "waiting": True,
            "action": p["action"],
            "msg": p["msg"]
        }

    # ============================================================
    # HELPERS
    # ============================================================

    async def _get_bg_page(self) -> Page:
        """Obtiene o crea página de fondo."""
        if self.bg_context and self.bg_context.pages:
            return self.bg_context.pages[0]
        if self.bg_context:
            return await self.bg_context.new_page()
        raise RuntimeError("Background context not initialized")

    def _get_active_page(self) -> Page:
        """Obtiene la pestaña activa más reciente, o la página principal del navegador."""
        if self.active_tabs:
            return list(self.active_tabs.values())[-1]
        return self.browser.page

    async def _inject_highlight_styles(self, page: Page):
        """Inyecta CSS para resaltado."""
        await page.evaluate(f"""
            () => {{
                if (document.getElementById('ai-styles')) return;
                const style = document.createElement('style');
                style.id = 'ai-styles';
                style.textContent = `{HIGHLIGHT_STYLES}`;
                document.head.appendChild(style);
            }}
        """)

    async def close_tab(self, orden: str):
        """Cierra una pestaña específica."""
        if orden in self.active_tabs:
            page = self.active_tabs.pop(orden)
            await page.close()

    async def close_all_tabs(self):
        """Cierra todas las pestañas activas."""
        for orden, page in list(self.active_tabs.items()):
            await page.close()
        self.active_tabs.clear()

        if self.bg_context:
            await self.bg_context.close()
            self.bg_context = None
