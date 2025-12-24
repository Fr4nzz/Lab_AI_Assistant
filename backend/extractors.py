"""
Page Data Extractors - Extract structured data from each page type.
Each function returns a structured dict ready for AI context.
"""
from typing import Optional
from playwright.async_api import Page


# JavaScript para extraer lista de órdenes
EXTRACT_ORDENES_JS = r"""
() => {
    const ordenes = [];
    const rows = document.querySelectorAll('table tbody tr');

    rows.forEach((row, index) => {
        if (index >= 20) return;  // Limitar a 20

        const cells = row.querySelectorAll('td');
        if (cells.length < 4) return;

        // Extraer ID interno del data-registro
        let id = null;
        const dr = row.querySelector('[data-registro]');
        if (dr) {
            try {
                const data = JSON.parse(dr.getAttribute('data-registro'));
                id = data.id;
            } catch(e) {}
        }

        // Datos del paciente (celda 2 contiene varias líneas)
        const pacienteCell = cells[2]?.innerText?.split('\n') || [];
        const cedula = pacienteCell[0]?.split(' ')[0] || '';
        const sexoEdad = pacienteCell[0]?.match(/([MF])\s*(\d+a)/) || [];

        ordenes.push({
            num: cells[0]?.innerText?.trim(),
            fecha: cells[1]?.innerText?.trim().replace(/\n/g, ' '),
            cedula: cedula,
            paciente: pacienteCell[1] || '',
            sexo: sexoEdad[1] || null,
            edad: sexoEdad[2] || null,
            estado: cells[3]?.innerText?.trim(),
            valor: cells[4]?.innerText?.trim(),
            id: id
        });
    });

    return ordenes;
}
"""

# JavaScript para extraer datos de reportes/resultados
EXTRACT_REPORTES_JS = r"""
() => {
    const examenes = [];
    let current = null;

    // Buscar filas con clase examen y parametro
    document.querySelectorAll('tr.examen, tr.parametro').forEach(row => {
        if (row.classList.contains('examen')) {
            // Guardar examen anterior si tiene campos
            if (current && current.campos.length > 0) {
                examenes.push(current);
            }

            // Extraer nombre y estado del examen
            const nombreText = row.innerText.trim().split('\n')[0];
            const badge = row.querySelector('.badge');
            const estado = badge?.innerText?.trim() || null;

            // Extraer tipo de muestra si está disponible
            const muestraCell = row.querySelector('td:nth-child(2)');
            const tipoMuestra = muestraCell?.innerText?.trim() || null;

            current = {
                nombre: nombreText.replace(estado || '', '').trim(),
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

            if (!select && !input) return;  // Solo campos editables

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

    // Agregar último examen
    if (current && current.campos.length > 0) {
        examenes.push(current);
    }

    // Extraer número de orden de la URL o del título
    let numeroOrden = null;
    const urlMatch = window.location.search.match(/numeroOrden=(\d+)/);
    if (urlMatch) numeroOrden = urlMatch[1];

    // Extraer nombre del paciente
    let paciente = null;
    const headerText = document.querySelector('.card-header, h1, h2')?.innerText || '';
    const pacienteMatch = headerText.match(/Paciente:\s*(.+)/i);
    if (pacienteMatch) paciente = pacienteMatch[1].trim();

    return {
        numero_orden: numeroOrden,
        paciente: paciente,
        examenes: examenes
    };
}
"""

# JavaScript para extraer datos de edición de orden
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

    // Número de orden
    const titulo = document.querySelector('h1, h2, .card-header');
    if (titulo) {
        const match = titulo.innerText.match(/(\d{7})/);
        if (match) result.numero_orden = match[1];
    }

    // Datos del paciente
    const idInput = document.querySelector('#identificacion');
    if (idInput) result.paciente.identificacion = idInput.value;

    // Buscar campos de nombre
    document.querySelectorAll('input').forEach(inp => {
        const id = inp.id?.toLowerCase() || '';
        if (id.includes('nombre') && !id.includes('apellido')) {
            result.paciente.nombres = inp.value;
        }
        if (id.includes('apellido')) {
            result.paciente.apellidos = inp.value;
        }
    });

    // Exámenes seleccionados
    const container = document.querySelector('#examenes-seleccionados');
    if (container) {
        container.querySelectorAll('tbody tr').forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 2) return;

            const nombre = cells[0]?.innerText?.trim();
            const valor = cells[1]?.innerText?.trim();
            const badge = cells[0]?.querySelector('.badge');
            const estado = badge?.innerText?.trim() || null;
            const canDelete = !row.querySelector('button[disabled]');

            if (nombre) {
                result.examenes.push({
                    nombre: nombre.replace(estado || '', '').trim(),
                    valor: valor,
                    estado: estado,
                    puede_eliminar: canDelete
                });
            }
        });
    }

    // Totales
    const descuentoInput = document.querySelector('#valor-descuento');
    if (descuentoInput) result.totales.descuento = descuentoInput.value;

    // Buscar totales en elementos bold
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
