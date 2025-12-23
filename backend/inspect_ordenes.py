"""
Script de inspección para la página de órdenes.
Ejecuta esto mientras estás logueado en el navegador para ver la estructura de la página.
Guarda el HTML completo para análisis offline por Claude Code.

Uso:
    cd backend
    python inspect_ordenes.py

O desde el root:
    python backend/inspect_ordenes.py
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright

# Obtener ruta absoluta del directorio del script
SCRIPT_DIR = Path(__file__).parent.absolute()
BROWSER_DATA_DIR = SCRIPT_DIR / "browser_data"
HTML_SAMPLES_DIR = SCRIPT_DIR / "html_samples"


async def save_page_html(page, prefix: str, suffix: str = ""):
    """Guarda el HTML completo de la página para análisis offline."""
    HTML_SAMPLES_DIR.mkdir(exist_ok=True)

    # Obtener el HTML completo
    html_content = await page.content()

    # Crear nombre de archivo con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix_part = f"_{suffix}" if suffix else ""
    filename = f"{prefix}{suffix_part}_{timestamp}.html"
    filepath = HTML_SAMPLES_DIR / filename

    # Guardar el archivo
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n💾 HTML guardado en: {filepath}")
    print(f"   Tamaño: {len(html_content):,} bytes")

    return filepath


async def inspect_ordenes_page():
    """Conectarse al navegador existente e inspeccionar la página de órdenes."""
    
    print(f"Usando browser_data en: {BROWSER_DATA_DIR}")
    
    async with async_playwright() as p:
        # Conectar al navegador con contexto persistente
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=False,
            channel="msedge",
            viewport={"width": 1280, "height": 900}
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Navegar a la página de órdenes
        print("Navegando a /ordenes...")
        await page.goto("https://laboratoriofranz.orion-labs.com/ordenes", timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        
        print(f"URL actual: {page.url}")
        print(f"Título: {await page.title()}")
        print("\n" + "="*80)
        
        # 1. Inspeccionar estructura de la tabla
        print("\n📋 ESTRUCTURA DE LA TABLA DE ÓRDENES:")
        print("-"*40)
        
        table_info = await page.evaluate("""
            () => {
                const table = document.querySelector('table');
                if (!table) return { error: 'No se encontró tabla' };
                
                // Headers
                const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.innerText.trim());
                
                // Rows
                const rows = Array.from(table.querySelectorAll('tbody tr')).slice(0, 10).map(row => {
                    const cells = Array.from(row.querySelectorAll('td'));
                    const rowData = {};
                    
                    cells.forEach((cell, index) => {
                        rowData[`col_${index}`] = {
                            text: cell.innerText.trim().substring(0, 100),
                            html_preview: cell.innerHTML.substring(0, 200),
                            classes: cell.className
                        };
                    });
                    
                    // Buscar data attributes útiles
                    const dataAttrs = {};
                    for (let attr of row.attributes) {
                        if (attr.name.startsWith('data-')) {
                            dataAttrs[attr.name] = attr.value.substring(0, 100);
                        }
                    }
                    
                    // Buscar enlaces o botones con data attributes
                    const actionElements = Array.from(row.querySelectorAll('a[data-registro], button[data-registro], a[href*="ordenes"]'));
                    const actions = actionElements.map(el => ({
                        tag: el.tagName,
                        href: el.href || null,
                        dataRegistro: el.getAttribute('data-registro')?.substring(0, 200),
                        text: el.innerText.trim().substring(0, 50)
                    }));
                    
                    return {
                        cells: rowData,
                        dataAttributes: dataAttrs,
                        actions: actions
                    };
                });
                
                return {
                    tableClasses: table.className,
                    headers: headers,
                    rowCount: table.querySelectorAll('tbody tr').length,
                    sampleRows: rows
                };
            }
        """)
        
        print(f"Clases de la tabla: {table_info.get('tableClasses', 'N/A')}")
        print(f"Headers encontrados: {table_info.get('headers', [])}")
        print(f"Total de filas: {table_info.get('rowCount', 0)}")
        
        print("\n📝 PRIMERAS 3 FILAS (muestra):")
        for i, row in enumerate(table_info.get('sampleRows', [])[:3]):
            print(f"\n  Fila {i+1}:")
            for col_key, col_data in row.get('cells', {}).items():
                print(f"    {col_key}: {col_data.get('text', '')[:60]}")
            if row.get('actions'):
                print(f"    Acciones: {row['actions']}")
        
        # 2. Buscar elementos de paginación
        print("\n" + "="*80)
        print("\n📄 PAGINACIÓN:")
        print("-"*40)
        
        pagination_info = await page.evaluate("""
            () => {
                const pagination = document.querySelector('.pagination, [class*="paginat"], nav[aria-label*="paginat"]');
                if (!pagination) return { found: false };
                
                return {
                    found: true,
                    html: pagination.innerHTML.substring(0, 500),
                    links: Array.from(pagination.querySelectorAll('a, button')).map(el => ({
                        text: el.innerText.trim(),
                        href: el.href || null
                    }))
                };
            }
        """)
        
        print(f"Paginación encontrada: {pagination_info.get('found', False)}")
        if pagination_info.get('links'):
            print(f"Links de paginación: {pagination_info['links'][:5]}")
        
        # 3. Buscar filtros y buscadores
        print("\n" + "="*80)
        print("\n🔍 FILTROS Y BUSCADORES:")
        print("-"*40)
        
        filters_info = await page.evaluate("""
            () => {
                const inputs = Array.from(document.querySelectorAll('input[type="text"], input[type="search"], select'));
                return inputs.map(el => ({
                    tag: el.tagName,
                    type: el.type,
                    id: el.id,
                    name: el.name,
                    placeholder: el.placeholder,
                    classes: el.className
                })).slice(0, 10);
            }
        """)
        
        for f in filters_info:
            print(f"  - {f}")
        
        # 4. Extraer datos limpios de las órdenes
        print("\n" + "="*80)
        print("\n✅ DATOS EXTRAÍDOS (formato limpio para IA):")
        print("-"*40)
        
        ordenes_limpias = await page.evaluate(r"""
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                const ordenes = [];
                
                rows.forEach((row, index) => {
                    if (index >= 20) return; // Limitar a 20
                    
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 3) return;
                    
                    // Intentar extraer datos comunes
                    const orden = {
                        numero: null,
                        paciente: null,
                        fecha: null,
                        estado: null,
                        examenes: [],
                        id_interno: null
                    };
                    
                    // Buscar número de orden (usualmente primera columna o tiene formato específico)
                    const textos = Array.from(cells).map(c => c.innerText.trim());
                    
                    // Buscar patrones
                    textos.forEach((texto, i) => {
                        // Número de orden (formato como 2512223)
                        if (/^\d{6,8}$/.test(texto)) {
                            orden.numero = texto;
                        }
                        // Fecha (formato DD/MM/YYYY o similar)
                        if (/\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}/.test(texto)) {
                            orden.fecha = texto;
                        }
                        // Estado (palabras clave)
                        if (/pendiente|procesad|validad|complet|entreg/i.test(texto)) {
                            orden.estado = texto;
                        }
                    });
                    
                    // Paciente suele ser el texto más largo
                    const textoLargo = textos.filter(t => t.length > 10 && !/\d{6,}/.test(t)).sort((a,b) => b.length - a.length)[0];
                    if (textoLargo) orden.paciente = textoLargo;
                    
                    // Buscar ID interno en data-registro
                    const dataRegistro = row.querySelector('[data-registro]');
                    if (dataRegistro) {
                        try {
                            const data = JSON.parse(dataRegistro.getAttribute('data-registro'));
                            orden.id_interno = data.id;
                        } catch(e) {}
                    }
                    
                    // Buscar link de edición para obtener ID
                    const editLink = row.querySelector('a[href*="/ordenes/"][href*="/edit"]');
                    if (editLink) {
                        const match = editLink.href.match(/ordenes\/(\d+)/);
                        if (match) orden.id_interno = match[1];
                    }
                    
                    if (orden.numero || orden.paciente) {
                        ordenes.push(orden);
                    }
                });
                
                return ordenes;
            }
        """)
        
        print(json.dumps(ordenes_limpias, indent=2, ensure_ascii=False))
        
        # Guardar resultado completo
        resultado = {
            "url": page.url,
            "table_info": table_info,
            "pagination": pagination_info,
            "filters": filters_info,
            "ordenes_extraidas": ordenes_limpias
        }
        
        with open("inspeccion_ordenes.json", "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        print("\n" + "="*80)
        print("✅ Resultado guardado en: inspeccion_ordenes.json")

        # Guardar HTML completo para análisis offline
        await save_page_html(page, "ordenes", "lista")
        print("="*80)

        # Mantener navegador abierto para inspección manual
        input("\nPresiona Enter para cerrar el navegador...")
        await context.close()


if __name__ == "__main__":
    asyncio.run(inspect_ordenes_page())
