"""
Script GENERALIZADO para inspeccionar la página de reportes/resultados.
Extrae TODOS los exámenes y campos disponibles, sin importar el tipo de examen.
"""
import asyncio
import sys
import json
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright

# Ruta del browser_data
SCRIPT_DIR = Path(__file__).parent.absolute()
BROWSER_DATA_DIR = SCRIPT_DIR / "browser_data"

# Orden a inspeccionar
NUMERO_ORDEN = "2501181"


async def inspect_reportes_page():
    """Navegar a la página de reportes y extraer estructura de exámenes."""
    
    print(f"Usando browser_data en: {BROWSER_DATA_DIR}")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=False,
            channel="msedge",
            viewport={"width": 1280, "height": 900}
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # 1. Navegar a la página de reportes
        url = f"https://laboratoriofranz.orion-labs.com/reportes2?numeroOrden={NUMERO_ORDEN}"
        print(f"\n📍 Navegando a: {url}")
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        
        # Esperar un poco más para que Vue.js renderice
        await page.wait_for_timeout(2000)
        
        print(f"   URL actual: {page.url}")
        
        # 2. Primero, explorar la estructura general de la página
        print("\n" + "="*70)
        print("🔍 EXPLORANDO ESTRUCTURA DE LA PÁGINA:")
        print("-"*70)
        
        estructura_general = await page.evaluate(r"""
            () => {
                const result = {
                    tables: [],
                    cards: [],
                    forms: []
                };
                
                // Buscar todas las tablas
                document.querySelectorAll('table').forEach((table, i) => {
                    const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.innerText.trim());
                    const rowCount = table.querySelectorAll('tbody tr').length;
                    const classes = table.className;
                    
                    // Obtener muestra de las primeras filas
                    const sampleRows = Array.from(table.querySelectorAll('tbody tr')).slice(0, 3).map(row => {
                        return {
                            classes: row.className,
                            cells: Array.from(row.querySelectorAll('td')).map(td => ({
                                text: td.innerText.trim().substring(0, 50),
                                hasSelect: td.querySelector('select') !== null,
                                hasInput: td.querySelector('input') !== null
                            }))
                        };
                    });
                    
                    result.tables.push({
                        index: i,
                        classes: classes,
                        headers: headers,
                        rowCount: rowCount,
                        sampleRows: sampleRows
                    });
                });
                
                // Buscar cards
                document.querySelectorAll('.card').forEach((card, i) => {
                    const header = card.querySelector('.card-header')?.innerText?.trim()?.substring(0, 100);
                    const hasTable = card.querySelector('table') !== null;
                    result.cards.push({
                        index: i,
                        header: header,
                        hasTable: hasTable
                    });
                });
                
                return result;
            }
        """)
        
        print(f"   Tablas encontradas: {len(estructura_general['tables'])}")
        for t in estructura_general['tables']:
            print(f"      [{t['index']}] Clases: {t['classes'][:50] if t['classes'] else 'N/A'}...")
            print(f"          Headers: {t['headers']}")
            print(f"          Filas: {t['rowCount']}")
            if t['sampleRows']:
                print(f"          Muestra fila 1 clases: {t['sampleRows'][0]['classes']}")
        
        print(f"\n   Cards encontrados: {len(estructura_general['cards'])}")
        for c in estructura_general['cards'][:5]:
            print(f"      [{c['index']}] {c['header'][:60] if c['header'] else 'Sin header'}...")
        
        # 3. Extraer exámenes de forma generalizada
        print("\n" + "="*70)
        print("📋 EXTRAYENDO EXÁMENES Y PARÁMETROS:")
        print("-"*70)
        
        examenes = await page.evaluate(r"""
            () => {
                const examenes = [];
                let currentExamen = null;
                
                // Estrategia 1: Buscar por clases .examen y .parametro
                document.querySelectorAll('tr.examen, tr.parametro').forEach(row => {
                    if (row.classList.contains('examen')) {
                        if (currentExamen && currentExamen.parametros.length > 0) {
                            examenes.push(currentExamen);
                        }
                        currentExamen = {
                            nombre: row.innerText.trim(),
                            parametros: [],
                            source: 'clase-examen'
                        };
                    } else if (row.classList.contains('parametro') && currentExamen) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            const param = {
                                nombre: cells[0]?.innerText?.trim(),
                                tipo: null,
                                valor: null,
                                opciones: null,
                                referencia: cells[2]?.innerText?.trim() || null
                            };
                            
                            const select = cells[1]?.querySelector('select');
                            const input = cells[1]?.querySelector('input');
                            
                            if (select) {
                                param.tipo = 'select';
                                param.valor = select.options[select.selectedIndex]?.text || select.value;
                                param.opciones = Array.from(select.options).map(o => o.text.trim()).filter(t => t);
                            } else if (input) {
                                param.tipo = 'input';
                                param.valor = input.value;
                            } else {
                                param.tipo = 'texto';
                                param.valor = cells[1]?.innerText?.trim();
                            }
                            
                            currentExamen.parametros.push(param);
                        }
                    }
                });
                if (currentExamen && currentExamen.parametros.length > 0) {
                    examenes.push(currentExamen);
                }
                
                // Estrategia 2: Si no encontramos nada, buscar por <strong> dentro de filas
                if (examenes.length === 0) {
                    currentExamen = null;
                    document.querySelectorAll('table tbody tr').forEach(row => {
                        const strong = row.querySelector('strong');
                        if (strong && !row.querySelector('input') && !row.querySelector('select')) {
                            // Es una cabecera de examen
                            if (currentExamen && currentExamen.parametros.length > 0) {
                                examenes.push(currentExamen);
                            }
                            currentExamen = {
                                nombre: strong.innerText.trim(),
                                parametros: [],
                                source: 'strong-tag'
                            };
                        } else if (currentExamen) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 2) {
                                const firstCell = cells[0]?.innerText?.trim();
                                if (firstCell && firstCell.length > 0 && firstCell.length < 100) {
                                    const param = {
                                        nombre: firstCell,
                                        tipo: null,
                                        valor: null,
                                        opciones: null,
                                        referencia: null
                                    };
                                    
                                    const select = cells[1]?.querySelector('select');
                                    const input = cells[1]?.querySelector('input');
                                    
                                    if (select) {
                                        param.tipo = 'select';
                                        param.valor = select.options[select.selectedIndex]?.text || select.value;
                                        param.opciones = Array.from(select.options).map(o => o.text.trim()).filter(t => t);
                                    } else if (input) {
                                        param.tipo = 'input';
                                        param.valor = input.value;
                                    }
                                    
                                    // Buscar referencia en celdas siguientes
                                    for (let i = 2; i < cells.length; i++) {
                                        const cellText = cells[i]?.innerText?.trim();
                                        if (cellText && cellText.match(/[\[\]0-9\-\.]/)) {
                                            param.referencia = cellText;
                                            break;
                                        }
                                    }
                                    
                                    if (param.tipo) {
                                        currentExamen.parametros.push(param);
                                    }
                                }
                            }
                        }
                    });
                    if (currentExamen && currentExamen.parametros.length > 0) {
                        examenes.push(currentExamen);
                    }
                }
                
                // Estrategia 3: Buscar CUALQUIER select o input en tablas
                if (examenes.length === 0) {
                    const inputs = document.querySelectorAll('table select, table input[type="text"], table input[type="number"]');
                    const genericExamen = {
                        nombre: "CAMPOS_ENCONTRADOS",
                        parametros: [],
                        source: 'generic-search'
                    };
                    
                    inputs.forEach(input => {
                        const row = input.closest('tr');
                        if (!row) return;
                        
                        const label = row.querySelector('td:first-child')?.innerText?.trim() || 
                                     input.getAttribute('name') ||
                                     input.getAttribute('id') ||
                                     'Campo sin nombre';
                        
                        const param = {
                            nombre: label.substring(0, 100),
                            tipo: input.tagName === 'SELECT' ? 'select' : 'input',
                            valor: input.tagName === 'SELECT' 
                                ? (input.options[input.selectedIndex]?.text || input.value)
                                : input.value,
                            opciones: input.tagName === 'SELECT' 
                                ? Array.from(input.options).map(o => o.text.trim()).filter(t => t)
                                : null
                        };
                        
                        genericExamen.parametros.push(param);
                    });
                    
                    if (genericExamen.parametros.length > 0) {
                        examenes.push(genericExamen);
                    }
                }
                
                return examenes;
            }
        """)
        
        print(f"   Total exámenes encontrados: {len(examenes)}")
        
        if len(examenes) == 0:
            print("\n   ⚠️ No se encontraron exámenes con las estrategias actuales.")
            print("   Vamos a inspeccionar el HTML crudo...")
            
            # Obtener HTML de la tabla principal
            html_debug = await page.evaluate(r"""
                () => {
                    const tables = document.querySelectorAll('table');
                    let html = "";
                    
                    tables.forEach((table, ti) => {
                        html += `\n\n===== TABLA ${ti} (classes: ${table.className}) =====\n`;
                        const rows = table.querySelectorAll('tbody tr');
                        for (let i = 0; i < Math.min(rows.length, 5); i++) {
                            html += `\n--- ROW ${i} (classes: ${rows[i].className}) ---\n`;
                            html += rows[i].innerHTML.substring(0, 300);
                        }
                    });
                    
                    return html || "No se encontraron tablas";
                }
            """)
            print("\n   📝 HTML de muestra:")
            print(html_debug[:3000])
        else:
            for examen in examenes:
                print(f"\n   📌 EXAMEN: {examen['nombre']}")
                print(f"      Fuente: {examen.get('source', 'N/A')}")
                print(f"      Parámetros: {len(examen['parametros'])}")
                
                for param in examen['parametros'][:15]:
                    tipo = param['tipo']
                    valor = param['valor'] or '(vacío)'
                    ref = f" [{param['referencia']}]" if param.get('referencia') else ""
                    
                    if tipo == 'select' and param.get('opciones'):
                        opciones = param['opciones'][:4]
                        opciones_str = ', '.join(opciones)
                        if len(param['opciones']) > 4:
                            opciones_str += f"... (+{len(param['opciones'])-4})"
                        print(f"      - {param['nombre']}: [{tipo}] = '{valor}'{ref}")
                        print(f"        Opciones: {opciones_str}")
                    else:
                        print(f"      - {param['nombre']}: [{tipo}] = '{valor}'{ref}")
                
                if len(examen['parametros']) > 15:
                    print(f"      ... y {len(examen['parametros']) - 15} más")
        
        # 4. Crear formato limpio para IA
        print("\n" + "="*70)
        print("🤖 FORMATO DIGERIDO PARA IA:")
        print("-"*70)
        
        formato_ia = {
            "numero_orden": NUMERO_ORDEN,
            "url": page.url,
            "examenes": []
        }
        
        for examen in examenes:
            examen_ia = {
                "nombre": examen['nombre'],
                "campos": []
            }
            
            for param in examen['parametros']:
                campo = {
                    "nombre": param['nombre'],
                    "tipo": param['tipo'],
                    "valor_actual": param['valor'] or None
                }
                
                if param.get('referencia'):
                    campo['referencia'] = param['referencia']
                
                if param['tipo'] == 'select' and param.get('opciones'):
                    campo['opciones_validas'] = param['opciones']
                
                examen_ia['campos'].append(campo)
            
            formato_ia['examenes'].append(examen_ia)
        
        # Imprimir formato IA
        formato_str = json.dumps(formato_ia, indent=2, ensure_ascii=False)
        print(formato_str[:3000])
        if len(formato_str) > 3000:
            print("... (truncado para consola)")
        
        # Guardar resultado completo
        with open("inspeccion_reportes.json", "w", encoding="utf-8") as f:
            json.dump({
                "numero_orden": NUMERO_ORDEN,
                "estructura_general": estructura_general,
                "examenes": examenes,
                "formato_ia": formato_ia
            }, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*70)
        print("✅ Resultado guardado en: inspeccion_reportes.json")
        print("="*70)
        
        input("\nPresiona Enter para cerrar el navegador...")
        await context.close()


if __name__ == "__main__":
    asyncio.run(inspect_reportes_page())
