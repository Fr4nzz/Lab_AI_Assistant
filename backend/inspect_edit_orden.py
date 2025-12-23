"""
Script para inspeccionar la página de EDICIÓN de una orden.
1. Busca órdenes con query "Chandi"
2. Navega a editar la 3ra orden encontrada
3. Extrae información relevante: paciente, exámenes seleccionados, valores, etc.
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


async def inspect_edit_orden():
    """Buscar orden y extraer información de la página de edición."""
    
    print(f"Usando browser_data en: {BROWSER_DATA_DIR}")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=False,
            channel="msedge",
            viewport={"width": 1280, "height": 900}
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # =====================================================
        # PASO 1: Buscar órdenes con "Chandi"
        # =====================================================
        print("\n" + "="*70)
        print("🔍 PASO 1: Buscando órdenes con 'Chandi'...")
        print("-"*70)
        
        await page.goto("https://laboratoriofranz.orion-labs.com/ordenes", timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        
        # Buscar el campo de búsqueda y escribir "Chandi"
        search_input = page.locator('input[placeholder*="Buscar por número de orden"]')
        await search_input.first.click()
        await search_input.first.fill("Chandi")
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        # Extraer las primeras 3 órdenes
        ordenes = await page.evaluate(r"""
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                const ordenes = [];
                
                for (let i = 0; i < Math.min(rows.length, 5); i++) {
                    const row = rows[i];
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 4) continue;
                    
                    const numero = cells[0]?.innerText?.trim();
                    const fecha = cells[1]?.innerText?.trim().replace(/\n/g, ' ');
                    const pacienteRaw = cells[2]?.innerText?.trim();
                    const pacienteLines = pacienteRaw?.split('\n') || [];
                    const estado = cells[3]?.innerText?.trim();
                    
                    // Extraer ID interno del data-registro
                    let idInterno = null;
                    const dataRegistro = row.querySelector('[data-registro]');
                    if (dataRegistro) {
                        try {
                            const data = JSON.parse(dataRegistro.getAttribute('data-registro'));
                            idInterno = data.id;
                        } catch(e) {}
                    }
                    
                    ordenes.push({
                        numero: numero,
                        fecha: fecha,
                        paciente_info: pacienteLines[0] || '',
                        paciente_nombre: pacienteLines[1] || '',
                        estado: estado,
                        id_interno: idInterno
                    });
                }
                
                return ordenes;
            }
        """)
        
        print(f"   Órdenes encontradas: {len(ordenes)}")
        for i, o in enumerate(ordenes[:5], 1):
            print(f"   [{i}] #{o['numero']} - {o['paciente_nombre']} (ID: {o['id_interno']})")
        
        if len(ordenes) < 3:
            print("   ❌ No hay suficientes órdenes. Se necesitan al menos 3.")
            await context.close()
            return
        
        # =====================================================
        # PASO 2: Navegar a editar la 3ra orden
        # =====================================================
        orden_seleccionada = ordenes[2]  # Índice 2 = tercera orden
        id_interno = orden_seleccionada['id_interno']
        
        print("\n" + "="*70)
        print(f"📝 PASO 2: Navegando a editar orden #{orden_seleccionada['numero']}")
        print(f"   ID interno: {id_interno}")
        print("-"*70)
        
        edit_url = f"https://laboratoriofranz.orion-labs.com/ordenes/{id_interno}/edit"
        print(f"   URL: {edit_url}")
        
        await page.goto(edit_url, timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(2000)  # Esperar Vue.js
        
        # =====================================================
        # PASO 3: Extraer información del paciente
        # =====================================================
        print("\n" + "="*70)
        print("👤 PASO 3: Extrayendo información del paciente...")
        print("-"*70)
        
        info_paciente = await page.evaluate(r"""
            () => {
                const info = {
                    identificacion: null,
                    nombres: null,
                    apellidos: null,
                    fecha_nacimiento: null,
                    edad: null,
                    sexo: null,
                    telefono: null,
                    email: null
                };
                
                // Buscar campos de paciente por ID o placeholder
                const identificacion = document.querySelector('#identificacion');
                if (identificacion) info.identificacion = identificacion.value;
                
                // Buscar en inputs del formulario
                document.querySelectorAll('input, select').forEach(el => {
                    const id = el.id?.toLowerCase() || '';
                    const name = el.name?.toLowerCase() || '';
                    const placeholder = el.placeholder?.toLowerCase() || '';
                    
                    if (id.includes('nombre') || name.includes('nombre')) {
                        if (id.includes('apellido') || name.includes('apellido')) {
                            info.apellidos = el.value;
                        } else {
                            info.nombres = el.value;
                        }
                    }
                    if (id.includes('apellido')) info.apellidos = el.value;
                    if (id.includes('telefono') || id.includes('celular')) info.telefono = el.value;
                    if (id.includes('email') || id.includes('correo')) info.email = el.value;
                    if (id.includes('sexo') || id.includes('genero')) {
                        info.sexo = el.tagName === 'SELECT' 
                            ? el.options[el.selectedIndex]?.text 
                            : el.value;
                    }
                });
                
                // Buscar texto visible del paciente
                const pacienteText = document.body.innerText;
                const edadMatch = pacienteText.match(/(\d+)\s*años?/i);
                if (edadMatch) info.edad = edadMatch[1] + ' años';
                
                return info;
            }
        """)
        
        print(f"   Identificación: {info_paciente.get('identificacion', 'N/A')}")
        print(f"   Nombres: {info_paciente.get('nombres', 'N/A')}")
        print(f"   Apellidos: {info_paciente.get('apellidos', 'N/A')}")
        
        # =====================================================
        # PASO 4: Extraer exámenes seleccionados
        # =====================================================
        print("\n" + "="*70)
        print("🧪 PASO 4: Extrayendo exámenes seleccionados...")
        print("-"*70)
        
        examenes_seleccionados = await page.evaluate(r"""
            () => {
                const examenes = [];
                
                // Buscar en el contenedor de exámenes seleccionados
                const container = document.querySelector('#examenes-seleccionados');
                if (!container) {
                    // Intentar encontrar por otra vía
                    const tables = document.querySelectorAll('table');
                    for (const table of tables) {
                        const rows = table.querySelectorAll('tbody tr');
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 2) {
                                const nombre = cells[0]?.innerText?.trim();
                                const valor = cells[1]?.innerText?.trim();
                                
                                // Verificar si parece un examen (tiene formato "CODIGO - NOMBRE")
                                if (nombre && nombre.includes(' - ')) {
                                    const deleteBtn = row.querySelector('button[title*="Eliminar"], button:has(i.fa-trash)');
                                    examenes.push({
                                        nombre: nombre,
                                        valor: valor,
                                        puede_eliminar: deleteBtn ? !deleteBtn.disabled : false,
                                        tiene_resultados: row.querySelector('.badge') !== null
                                    });
                                }
                            }
                        }
                    }
                    return examenes;
                }
                
                // Si encontramos el contenedor específico
                const rows = container.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 2) return;
                    
                    const nombreCell = cells[0];
                    const valorCell = cells[1];
                    const accionCell = cells[2];
                    
                    // Extraer nombre del examen
                    let nombre = nombreCell?.innerText?.trim() || '';
                    
                    // Verificar si tiene badge de estado (validado, pendiente, etc.)
                    const badge = nombreCell?.querySelector('.badge');
                    const estado = badge?.innerText?.trim() || null;
                    
                    // Extraer valor
                    const valor = valorCell?.innerText?.trim() || '0.00';
                    
                    // Verificar si se puede eliminar
                    const deleteBtn = accionCell?.querySelector('button[title*="Eliminar"], button:has(i.fa-trash)');
                    const puedeEliminar = deleteBtn ? !deleteBtn.disabled : false;
                    
                    if (nombre) {
                        examenes.push({
                            nombre: nombre.replace(estado || '', '').trim(),
                            valor: valor,
                            estado: estado,
                            puede_eliminar: puedeEliminar
                        });
                    }
                });
                
                return examenes;
            }
        """)
        
        print(f"   Total exámenes: {len(examenes_seleccionados)}")
        for ex in examenes_seleccionados:
            estado = f" ({ex.get('estado', '')})" if ex.get('estado') else ""
            eliminar = "🗑️" if ex.get('puede_eliminar') else "🔒"
            print(f"   {eliminar} {ex['nombre']}{estado} - ${ex.get('valor', '0.00')}")
        
        # =====================================================
        # PASO 5: Extraer totales y otros datos
        # =====================================================
        print("\n" + "="*70)
        print("💰 PASO 5: Extrayendo totales y otros datos...")
        print("-"*70)
        
        otros_datos = await page.evaluate(r"""
            () => {
                const datos = {
                    fecha_orden: null,
                    numero_orden: null,
                    subtotal: null,
                    descuento: null,
                    total: null,
                    observaciones: null,
                    categoria: null
                };
                
                // Fecha de orden
                const fechaInput = document.querySelector('#fecha-orden');
                if (fechaInput) datos.fecha_orden = fechaInput.value;
                
                // Número de orden (buscar en el título o breadcrumb)
                const titulo = document.querySelector('h1, h2, .card-header');
                if (titulo) {
                    const match = titulo.innerText.match(/(\d{7})/);
                    if (match) datos.numero_orden = match[1];
                }
                
                // Buscar totales
                document.querySelectorAll('*').forEach(el => {
                    const text = el.innerText?.toLowerCase() || '';
                    if (text.includes('subtotal') && el.nextElementSibling) {
                        datos.subtotal = el.nextElementSibling.innerText?.trim();
                    }
                    if (text === 'total' && el.nextElementSibling) {
                        datos.total = el.nextElementSibling.innerText?.trim();
                    }
                });
                
                // Descuento
                const descuentoInput = document.querySelector('#valor-descuento');
                if (descuentoInput) datos.descuento = descuentoInput.value;
                
                // Observaciones
                const obsInput = document.querySelector('#observaciones-recibo, textarea[name*="observ"]');
                if (obsInput) datos.observaciones = obsInput.value;
                
                // Buscar totales de otra manera
                const totalElements = document.querySelectorAll('.fw-bold, .fs-5');
                totalElements.forEach(el => {
                    const text = el.innerText?.trim() || '';
                    if (text.startsWith('$')) {
                        datos.total = text;
                    }
                });
                
                return datos;
            }
        """)
        
        print(f"   Número orden: {otros_datos.get('numero_orden', 'N/A')}")
        print(f"   Fecha: {otros_datos.get('fecha_orden', 'N/A')}")
        print(f"   Subtotal: {otros_datos.get('subtotal', 'N/A')}")
        print(f"   Descuento: {otros_datos.get('descuento', 'N/A')}")
        print(f"   Total: {otros_datos.get('total', 'N/A')}")
        
        # =====================================================
        # PASO 6: Extraer botones de acción disponibles
        # =====================================================
        print("\n" + "="*70)
        print("🔘 PASO 6: Botones de acción disponibles...")
        print("-"*70)
        
        botones = await page.evaluate(r"""
            () => {
                const botones = [];
                
                // Buscar botones principales
                const selectores = [
                    '#crear-orden',
                    '#guardar-orden', 
                    'button[type="submit"]',
                    'button:has(i.fa-save)',
                    'a[href*="/reportes2"]'
                ];
                
                document.querySelectorAll('button, a.btn').forEach(btn => {
                    const texto = btn.innerText?.trim() || btn.title || '';
                    const id = btn.id || '';
                    const disabled = btn.disabled || btn.classList.contains('disabled');
                    
                    if (texto || id) {
                        botones.push({
                            texto: texto.substring(0, 50),
                            id: id,
                            disabled: disabled,
                            tipo: btn.tagName
                        });
                    }
                });
                
                return botones.slice(0, 15); // Limitar a 15
            }
        """)
        
        for btn in botones:
            estado = "🔴" if btn['disabled'] else "🟢"
            print(f"   {estado} [{btn.get('id', '')}] {btn['texto'][:40]}")
        
        # =====================================================
        # PASO 7: Generar formato digerido para IA
        # =====================================================
        print("\n" + "="*70)
        print("🤖 FORMATO DIGERIDO PARA IA:")
        print("-"*70)
        
        formato_ia = {
            "tipo_pagina": "edicion_orden",
            "url": page.url,
            "orden": {
                "numero": orden_seleccionada['numero'],
                "id_interno": id_interno,
                "fecha": otros_datos.get('fecha_orden'),
                "estado": orden_seleccionada.get('estado')
            },
            "paciente": {
                "identificacion": info_paciente.get('identificacion'),
                "nombre_completo": orden_seleccionada.get('paciente_nombre'),
                "info_adicional": orden_seleccionada.get('paciente_info')
            },
            "examenes": [
                {
                    "nombre": ex['nombre'],
                    "valor": ex.get('valor'),
                    "estado": ex.get('estado'),
                    "puede_eliminar": ex.get('puede_eliminar', False)
                }
                for ex in examenes_seleccionados
            ],
            "totales": {
                "subtotal": otros_datos.get('subtotal'),
                "descuento": otros_datos.get('descuento'),
                "total": otros_datos.get('total')
            },
            "acciones_disponibles": {
                "guardar": "button#crear-orden o button[type='submit']",
                "agregar_examen": "input#buscar-examen-input",
                "eliminar_examen": "button[title='Eliminar examen'] en cada fila",
                "ir_a_reportar": "click en botón 'Reportar y validar'"
            }
        }
        
        formato_str = json.dumps(formato_ia, indent=2, ensure_ascii=False)
        print(formato_str)
        
        # Guardar resultado
        with open("inspeccion_edit_orden.json", "w", encoding="utf-8") as f:
            json.dump({
                "orden_seleccionada": orden_seleccionada,
                "info_paciente": info_paciente,
                "examenes_seleccionados": examenes_seleccionados,
                "otros_datos": otros_datos,
                "botones": botones,
                "formato_ia": formato_ia
            }, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*70)
        print("✅ Resultado guardado en: inspeccion_edit_orden.json")
        print("="*70)
        
        input("\nPresiona Enter para cerrar el navegador...")
        await context.close()


if __name__ == "__main__":
    asyncio.run(inspect_edit_orden())
