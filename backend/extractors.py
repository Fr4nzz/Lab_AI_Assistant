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

# JavaScript para extraer datos de reportes/resultados (mejorado)
EXTRACT_REPORTES_JS = r"""
() => {
    const examenes = [];
    let current = null;

    // List of known sample types
    const tiposMuestra = ['Sangre Total EDTA', 'Suero', 'Orina', 'Heces', 'Plasma'];

    document.querySelectorAll('tr.examen, tr.parametro').forEach(row => {
        if (row.classList.contains('examen')) {
            if (current && current.campos.length > 0) {
                examenes.push(current);
            }

            // Get exam name from <strong> tag (clean)
            const strong = row.querySelector('strong');
            const nombre = strong?.innerText?.trim() || '';

            // Get status from badge
            const badge = row.querySelector('.badge');
            const estado = badge?.innerText?.trim() || null;

            // Get sample type from cell text
            let tipoMuestra = null;
            const fullText = row.innerText;
            for (const tipo of tiposMuestra) {
                if (fullText.includes(tipo)) {
                    tipoMuestra = tipo;
                    break;
                }
            }

            current = {
                nombre: nombre,
                estado: estado,
                tipo_muestra: tipoMuestra,
                campos: []
            };
        } else if (row.classList.contains('parametro') && current) {
            const cells = row.querySelectorAll('td');
            if (cells.length < 2) return;

            const nombreCampo = cells[0]?.innerText?.trim();
            const select = cells[1]?.querySelector('select');
            const input = cells[1]?.querySelector('input');

            if (!select && !input) return;

            const campo = {
                f: nombreCampo,
                tipo: select ? 'select' : 'input',
                val: null,
                opciones: null,
                ref: cells[2]?.innerText?.trim() || null
            };

            if (select) {
                campo.val = select.options[select.selectedIndex]?.text || '';
                campo.opciones = Array.from(select.options)
                    .map(o => o.text.trim())
                    .filter(t => t);
            } else if (input) {
                campo.val = input.value;
            }

            current.campos.push(campo);
        }
    });

    if (current && current.campos.length > 0) {
        examenes.push(current);
    }

    // Get order number from URL
    let numeroOrden = null;
    const urlMatch = window.location.search.match(/numeroOrden=(\d+)/);
    if (urlMatch) numeroOrden = urlMatch[1];

    // Get patient name from span.paciente (find one with actual name)
    let paciente = null;
    document.querySelectorAll('span.paciente').forEach(span => {
        const text = span.innerText?.trim();
        if (text && text !== 'Paciente' && text.length > 3) {
            paciente = text;
        }
    });

    return {
        numero_orden: numeroOrden,
        paciente: paciente,
        examenes: examenes
    };
}
"""

# JavaScript para extraer datos de edición de orden (mejorado)
EXTRACT_ORDEN_EDIT_JS = r"""
() => {
    const result = {
        numero_orden: null,
        paciente: {
            identificacion: null,
            nombres: null,
            apellidos: null
        },
        examenes: [],
        totales: {
            subtotal: null,
            descuento: null,
            total: null
        }
    };

    // Get order number from URL or page content
    const urlMatch = window.location.pathname.match(/ordenes\/(\d+)/);
    if (urlMatch) result.numero_orden = urlMatch[1];

    // Get patient name from span.paciente (find one with actual name)
    document.querySelectorAll('span.paciente').forEach(span => {
        const text = span.innerText?.trim();
        if (text && text !== 'Paciente' && text.length > 3) {
            result.paciente.nombres = text;
        }
    });

    // Get patient ID from visible cedula field
    const cedulaMatch = document.body.innerText.match(/\b(\d{10})\b/);
    if (cedulaMatch) {
        result.paciente.identificacion = cedulaMatch[1];
    }

    // Exams from #examenes-seleccionados
    const container = document.querySelector('#examenes-seleccionados');
    if (container) {
        container.querySelectorAll('tbody tr').forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 1) return;

            // First cell format: "CODE - NAME|V|1|time"
            const cellText = cells[0]?.innerText || '';
            const parts = cellText.split('\n').map(p => p.trim()).filter(p => p);

            // First part is "CODE - NAME"
            let nombreRaw = parts[0] || '';
            let codigo = null;
            let nombre = nombreRaw;

            if (nombreRaw.includes(' - ')) {
                const splitName = nombreRaw.split(' - ');
                codigo = splitName[0].trim();
                nombre = splitName.slice(1).join(' - ').trim();
            }

            // Find estado (V = Validado, P = Pendiente)
            let estado = null;
            for (const part of parts.slice(1)) {
                if (part === 'V') { estado = 'Validado'; break; }
                if (part === 'P') { estado = 'Pendiente'; break; }
            }

            // Valor from second cell
            const valor = cells[1]?.innerText?.trim() || null;

            if (nombre) {
                result.examenes.push({
                    codigo: codigo,
                    nombre: nombre,
                    valor: valor,
                    estado: estado
                });
            }
        });
    }

    // Totales
    const descuentoInput = document.querySelector('#valor-descuento');
    if (descuentoInput) result.totales.descuento = descuentoInput.value;

    document.querySelectorAll('.fw-bold, .fs-5').forEach(el => {
        const text = el.innerText?.trim() || '';
        if (text.startsWith('$')) {
            result.totales.total = text;
        }
    });

    return result;
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
        await self.page.wait_for_timeout(1000)  # Esperar Vue.js

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
        await self.page.wait_for_timeout(2000)  # Vue.js necesita más tiempo

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
        await self.page.wait_for_timeout(1500)

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
        await self.page.wait_for_timeout(1000)

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
