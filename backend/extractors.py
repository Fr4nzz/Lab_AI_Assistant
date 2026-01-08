"""
Page Data Extractors - Extract structured data from each page type.
Each function returns a structured dict ready for AI context.
Improved based on actual HTML structure analysis.
"""
from typing import Optional
from playwright.async_api import Page


# JavaScript para extraer lista de órdenes (mejorado)
EXTRACT_ORDENES_JS = r"""
() => {
    const ordenes = [];

    // Find main orders table (has headers: No., Fecha, Paciente, Estado, Valor)
    const tables = document.querySelectorAll('table');
    let ordersTable = null;

    for (const table of tables) {
        const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.innerText.trim());
        if (headers.includes('No.') && headers.includes('Paciente')) {
            ordersTable = table;
            break;
        }
    }

    if (!ordersTable) return ordenes;

    const rows = ordersTable.querySelectorAll('tbody tr');

    rows.forEach((row, index) => {
        if (index >= 20) return;

        const cells = row.querySelectorAll('td');
        if (cells.length < 5) return;

        // Extract ID from data-registro (in cell 3)
        let id = null;
        const dr = cells[3]?.querySelector('[data-registro]');
        if (dr) {
            try {
                const data = JSON.parse(dr.getAttribute('data-registro'));
                id = data.id;
            } catch(e) {}
        }

        // Order number - clean separator
        const numText = cells[0]?.innerText?.replace(/\s+/g, '').trim() || '';

        // Date - format properly
        const fechaText = cells[1]?.innerText?.replace(/\n/g, ' ').trim() || '';

        // Patient cell - parse complex structure
        // Format: "CEDULA E: AGE S: SEX NAME buttons..."
        const pacienteText = cells[2]?.innerText || '';
        const parts = pacienteText.split('\n').map(p => p.trim()).filter(p => p);

        let cedula = parts[0]?.split(' ')[0] || '';
        let edad = null;
        let sexo = null;
        let nombre = '';

        // Parse patient info
        for (const part of parts) {
            // Match age pattern like "47a"
            const ageMatch = part.match(/^(\d+a)$/);
            if (ageMatch) {
                edad = ageMatch[1];
                continue;
            }
            // Match sex
            if (part === 'M' || part === 'F') {
                sexo = part;
                continue;
            }
            // Name is usually all caps, longer than 5 chars, no digits
            if (part.length > 5 && part === part.toUpperCase() && !/\d/.test(part) && !part.includes('E:') && !part.includes('S:')) {
                nombre = part;
                break;
            }
        }

        // Estado from badge
        const estadoBadge = cells[3]?.querySelector('.badge');
        const estado = estadoBadge?.innerText?.trim() || cells[3]?.innerText?.trim() || '';

        // Valor
        const valor = cells[4]?.innerText?.trim() || '';

        ordenes.push({
            num: numText,
            fecha: fechaText,
            cedula: cedula,
            paciente: nombre,
            sexo: sexo,
            edad: edad,
            estado: estado,
            valor: valor,
            id: id
        });
    });

    return ordenes;
}
"""

# JavaScript para extraer datos de reportes/resultados (COMPACT FORMAT)
# Keys: ord=order, pat=patient, exm=exams, nam=name, sts=Val|Pnd, fld=fields, fnm=field name, val=value, ref=reference, opt=options
EXTRACT_REPORTES_JS = r"""
() => {
    const exm = [];
    let current = null;

    document.querySelectorAll('tr.examen, tr.parametro').forEach(row => {
        if (row.classList.contains('examen')) {
            if (current && current.fld.length > 0) {
                exm.push(current);
            }

            // Get exam name from <strong> tag
            const strong = row.querySelector('strong');
            const nam = strong?.innerText?.trim() || '';

            // Get status from badge (compact: Val/Pnd)
            const badge = row.querySelector('.badge');
            const estadoText = badge?.innerText?.trim();
            const sts = estadoText === 'Validado' ? 'Val' :
                       estadoText === 'Pendiente' ? 'Pnd' : null;

            current = { nam, sts, fld: [] };
        } else if (row.classList.contains('parametro') && current) {
            const cells = row.querySelectorAll('td');
            if (cells.length < 2) return;

            const fnm = cells[0]?.innerText?.trim();
            const select = cells[1]?.querySelector('select');
            const input = cells[1]?.querySelector('input');

            if (!select && !input) return;

            const campo = { fnm };

            if (select) {
                const selOpt = select.options[select.selectedIndex];
                campo.val = selOpt?.text || '';
                campo.opt = Array.from(select.options)
                    .map(o => o.text.trim())
                    .filter(t => t);
            } else {
                campo.val = input.value;
            }

            // Only include ref if present
            const ref = cells[2]?.innerText?.trim();
            if (ref) campo.ref = ref;

            current.fld.push(campo);
        }
    });

    if (current && current.fld.length > 0) {
        exm.push(current);
    }

    // Get order number from URL
    let ord = null;
    const urlMatch = window.location.search.match(/numeroOrden=(\d+)/);
    if (urlMatch) ord = urlMatch[1];

    // Get patient name from span.paciente
    let pat = null;
    document.querySelectorAll('span.paciente').forEach(span => {
        const text = span.innerText?.trim();
        if (text && text !== 'Paciente' && text.length > 3) {
            pat = text;
        }
    });

    return { ord, pat, exm };
}
"""

# JavaScript para extraer datos de edición de orden (COMPACT FORMAT)
# Keys: ord=order, ced=cedula, pat=patient, exm=exams, cod=code, nam=name, prc=price, sts=Val|Pnd, tot=total
EXTRACT_ORDEN_EDIT_JS = r"""
() => {
    // Get order number from URL
    let ord = null;
    const urlMatch = window.location.pathname.match(/ordenes\/(\d+)/);
    if (urlMatch) ord = urlMatch[1];

    // Get patient name from span.paciente
    let pat = null;
    document.querySelectorAll('span.paciente').forEach(span => {
        const text = span.innerText?.trim();
        if (text && text !== 'Paciente' && text.length > 3) {
            pat = text;
        }
    });

    // Get cedula from visible field
    let ced = null;
    const cedulaMatch = document.body.innerText.match(/\b(\d{10})\b/);
    if (cedulaMatch) ced = cedulaMatch[1];

    // Exams from #examenes-seleccionados
    const exm = [];
    const container = document.querySelector('#examenes-seleccionados');
    if (container) {
        container.querySelectorAll('tbody tr').forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 1) return;

            const cellText = cells[0]?.innerText || '';
            const parts = cellText.split('\n').map(p => p.trim()).filter(p => p);

            let nombreRaw = parts[0] || '';
            let cod = null;
            let nam = nombreRaw;

            if (nombreRaw.includes(' - ')) {
                const splitName = nombreRaw.split(' - ');
                cod = splitName[0].trim();
                nam = splitName.slice(1).join(' - ').trim();
            }

            // Status (V = Val, P = Pnd)
            let sts = null;
            for (const part of parts.slice(1)) {
                if (part === 'V') { sts = 'Val'; break; }
                if (part === 'P') { sts = 'Pnd'; break; }
            }

            const prc = cells[1]?.innerText?.trim() || null;

            if (cod) {
                const exam = { cod, nam };
                if (sts) exam.sts = sts;
                if (prc) exam.prc = prc;
                exm.push(exam);
            }
        });
    }

    // Total
    let tot = null;
    document.querySelectorAll('.fw-bold, .fs-5').forEach(el => {
        const text = el.innerText?.trim() || '';
        if (text.startsWith('$') && !tot) tot = text;
    });

    return { ord, ced, pat, exm, tot };
}
"""

# JavaScript para extraer exámenes disponibles
# Internal format includes button_id for clicking, codigo for matching
# AI output is filtered in _get_available_exams_impl to compact format
EXTRACT_AVAILABLE_EXAMS_JS = r"""
() => {
    const exams = [];

    // Find the search input to locate the correct table
    const searchInput = document.querySelector('#buscar-examen-input');
    if (!searchInput) return exams;

    // Find the table containing available exams (near the search input)
    const container = searchInput.closest('.table-responsive') || searchInput.closest('.col-12');
    if (!container) return exams;

    const table = container.querySelector('table');
    if (!table) return exams;

    // Extract exam rows - each row has a div with title and a button id="examen-N"
    table.querySelectorAll('tbody tr').forEach((row, index) => {
        const td = row.querySelector('td');
        const div = td?.querySelector('div[title]');
        const button = row.querySelector('button[id^="examen-"]');

        if (div && button) {
            const fullName = div.getAttribute('title') || '';
            const text = div.innerText?.trim() || '';

            // Parse CODE - NAME format
            let codigo = null;
            let nombre = fullName;

            if (text.includes(' - ')) {
                const parts = text.split(' - ');
                codigo = parts[0].trim();
                nombre = parts.slice(1).join(' - ').trim();
                // Clean up trailing icons/text
                nombre = nombre.replace(/\s*Se remite.*$/i, '').trim();
            }

            // Check if exam is remitted (sent to external lab)
            const remitido = row.querySelector('i.fa-shipping-fast') !== null;

            // Keep full format for internal use (button clicking)
            exams.push({
                codigo: codigo,
                nombre: nombre || fullName,
                button_id: button.id,
                remitido: remitido
            });
        }
    });

    return exams;
}
"""

# JavaScript para extraer exámenes ya agregados a la orden (COMPACT FORMAT)
# Keys: cod=code, nam=name, prc=price, sts=Val|Pnd
EXTRACT_ADDED_EXAMS_JS = r"""
() => {
    const exm = [];

    const container = document.querySelector('#examenes-seleccionados');
    if (!container) return exm;

    container.querySelectorAll('tbody tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 1) return;

        const cellText = cells[0]?.innerText || '';
        const parts = cellText.split('\n').map(p => p.trim()).filter(p => p);

        let nombreRaw = parts[0] || '';
        let cod = null;
        let nam = nombreRaw;

        if (nombreRaw.includes(' - ')) {
            const splitName = nombreRaw.split(' - ');
            cod = splitName[0].trim();
            nam = splitName.slice(1).join(' - ').trim();
        }

        // Status (V = Val, P = Pnd)
        let sts = null;
        for (const part of parts.slice(1)) {
            if (part === 'V') { sts = 'Val'; break; }
            if (part === 'P') { sts = 'Pnd'; break; }
        }

        const prc = cells[1]?.innerText?.trim() || null;

        if (cod) {
            const exam = { cod, nam };
            if (sts) exam.sts = sts;
            if (prc) exam.prc = prc;
            exm.push(exam);
        }
    });

    return exm;
}
"""


class PageDataExtractor:
    """Extractor de datos estructurados de cada tipo de página."""

    def __init__(self, page: Page):
        self.page = page

    async def detect_page_type(self) -> str:
        """Detecta el tipo de página actual basado en la URL."""
        url = self.page.url

        if '/ordenes/create' in url:
            return 'orden_create'
        elif '/ordenes/' in url and '/edit' in url:
            return 'orden_edit'
        elif '/ordenes' in url:
            return 'ordenes_list'
        elif '/reportes2' in url:
            return 'reportes'
        elif '/login' in url or 'login' in url.lower():
            return 'login'
        else:
            return 'unknown'

    async def extract_ordenes_list(self, limit: int = 20) -> dict:
        """
        Extrae lista de órdenes de la página /ordenes.

        Returns:
            {
                "page_type": "ordenes_list",
                "ordenes": [...],
                "total_ordenes": int
            }
        """
        # Wait for table rows to appear (Vue.js rendered) instead of arbitrary timeout
        try:
            await self.page.locator("table tbody tr, .order-row").first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass  # Table might be empty, continue anyway

        ordenes = await self.page.evaluate(EXTRACT_ORDENES_JS)

        return {
            "page_type": "ordenes_list",
            "ordenes": ordenes[:limit],
            "total_ordenes": len(ordenes)
        }

    async def extract_reportes(self) -> dict:
        """
        Extrae datos de exámenes de la página /reportes2.

        Returns:
            {
                "page_type": "reportes",
                "numero_orden": str,
                "paciente": str,
                "examenes": [
                    {
                        "nombre": str,
                        "estado": str,
                        "tipo_muestra": str,
                        "campos": [
                            {"f": str, "tipo": str, "val": str, "ref": str, "opciones": list}
                        ]
                    }
                ]
            }
        """
        # Wait for exam table to render instead of arbitrary 2s timeout
        try:
            await self.page.locator("tr.examen, .exam-row").first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass  # Page might have no exams, continue anyway

        data = await self.page.evaluate(EXTRACT_REPORTES_JS)
        data["page_type"] = "reportes"

        return data

    async def extract_orden_edit(self) -> dict:
        """
        Extrae datos de la página de edición de orden /ordenes/{id}/edit.

        Returns:
            {
                "page_type": "orden_edit",
                "numero_orden": str,
                "paciente": {...},
                "examenes": [...],
                "totales": {...}
            }
        """
        # Wait for order form to render instead of arbitrary 1.5s timeout
        try:
            await self.page.locator("#identificacion, .examen-row, tr.examen").first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass  # Continue anyway

        data = await self.page.evaluate(EXTRACT_ORDEN_EDIT_JS)
        data["page_type"] = "orden_edit"

        return data

    async def extract_orden_create(self) -> dict:
        """
        Extrae estado del formulario de creación de orden.

        Returns:
            {
                "page_type": "orden_create",
                "paciente_cargado": bool,
                "examenes_seleccionados": [...],
                "totales": {...}
            }
        """
        # Wait for create form to render instead of arbitrary 1s timeout
        try:
            await self.page.locator("#identificacion, #buscar-examen-input").first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass  # Continue anyway

        data = await self.page.evaluate(r"""
            () => {
                const result = {
                    paciente_cargado: false,
                    examenes_seleccionados: [],
                    totales: { subtotal: null, total: null }
                };

                // Verificar si hay paciente cargado
                const nombreInput = document.querySelector('#nombres, input[id*="nombre"]');
                if (nombreInput && nombreInput.value) {
                    result.paciente_cargado = true;
                }

                // Exámenes seleccionados
                const container = document.querySelector('#examenes-seleccionados');
                if (container) {
                    container.querySelectorAll('tbody tr').forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            result.examenes_seleccionados.push({
                                nombre: cells[0]?.innerText?.trim(),
                                valor: cells[1]?.innerText?.trim()
                            });
                        }
                    });
                }

                return result;
            }
        """)

        data["page_type"] = "orden_create"
        return data

    async def extract_available_exams(self) -> dict:
        """
        Extrae lista de exámenes disponibles para agregar a una orden.
        Solo funciona en páginas de crear/editar orden.

        Returns:
            {
                "page_type": "available_exams",
                "examenes": [
                    {"codigo": str, "nombre": str, "button_id": str, "remitido": bool}
                ],
                "total": int
            }
        """
        # Wait for exam search input to be ready instead of arbitrary 500ms
        try:
            await self.page.locator("#buscar-examen-input").wait_for(state="visible", timeout=3000)
        except Exception:
            pass  # Continue anyway

        exams = await self.page.evaluate(EXTRACT_AVAILABLE_EXAMS_JS)

        return {
            "page_type": "available_exams",
            "examenes": exams,
            "total": len(exams)
        }

    async def extract_added_exams(self) -> dict:
        """
        Extrae lista de exámenes ya agregados a la orden actual.
        Solo funciona en páginas de crear/editar orden.

        Returns:
            {
                "page_type": "added_exams",
                "examenes": [
                    {"codigo": str, "nombre": str, "valor": str, "estado": str, "can_remove": bool}
                ],
                "total": int
            }
        """
        # Wait for selected exams container instead of arbitrary 500ms
        try:
            await self.page.locator("#examenes-seleccionados, .selected-exams").first.wait_for(state="visible", timeout=3000)
        except Exception:
            pass  # May have no exams selected, continue anyway

        exams = await self.page.evaluate(EXTRACT_ADDED_EXAMS_JS)

        return {
            "page_type": "added_exams",
            "examenes": exams,
            "total": len(exams)
        }

    async def extract_current_page(self) -> dict:
        """
        Detecta el tipo de página y extrae los datos correspondientes.
        """
        page_type = await self.detect_page_type()

        if page_type == "ordenes_list":
            return await self.extract_ordenes_list()
        elif page_type == "reportes":
            return await self.extract_reportes()
        elif page_type == "orden_edit":
            return await self.extract_orden_edit()
        elif page_type == "orden_create":
            return await self.extract_orden_create()
        else:
            return {
                "page_type": page_type,
                "url": self.page.url
            }
