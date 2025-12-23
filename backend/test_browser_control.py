"""
Script de prueba: Buscar paciente y extraer órdenes.
Prueba que el código puede controlar el navegador correctamente.
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


async def test_search_and_extract():
    """Buscar paciente y extraer datos de las primeras 3 órdenes."""
    
    print(f"Usando browser_data en: {BROWSER_DATA_DIR}")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=False,
            channel="msedge",
            viewport={"width": 1280, "height": 900}
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # 1. Navegar a órdenes
        print("\n📍 Navegando a /ordenes...")
        await page.goto("https://laboratoriofranz.orion-labs.com/ordenes", timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        print(f"   URL: {page.url}")
        
        # 2. Buscar el input de búsqueda
        print("\n🔍 Buscando el campo de búsqueda...")
        
        # Selector más específico para el input de búsqueda
        search_input = page.locator('input[placeholder*="Buscar por número de orden"]')
        
        # Verificar que existe
        count = await search_input.count()
        print(f"   Encontrados: {count} campo(s) de búsqueda")
        
        if count == 0:
            # Intentar selector alternativo
            search_input = page.locator('input[placeholder*="paciente"]')
            count = await search_input.count()
            print(f"   Selector alternativo: {count} campo(s)")
        
        if count == 0:
            print("   ❌ No se encontró el campo de búsqueda")
            await context.close()
            return
        
        # 3. Escribir "Chandi" en el campo de búsqueda
        print("\n⌨️ Escribiendo 'Chandi' en el campo de búsqueda...")
        await search_input.first.click()
        await search_input.first.fill("Chandi")
        print("   ✅ Texto ingresado")
        
        # 4. Presionar Enter
        print("\n↩️ Presionando Enter...")
        await page.keyboard.press("Enter")
        
        # 5. Esperar a que carguen los resultados
        print("\n⏳ Esperando resultados...")
        await page.wait_for_timeout(2000)  # Esperar 2 segundos para que cargue
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        # 6. Extraer las primeras 3 órdenes
        print("\n📋 Extrayendo las primeras 3 órdenes:")
        print("-" * 60)
        
        ordenes = await page.evaluate(r"""
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                const ordenes = [];
                
                for (let i = 0; i < Math.min(rows.length, 3); i++) {
                    const row = rows[i];
                    const cells = row.querySelectorAll('td');
                    
                    if (cells.length < 4) continue;
                    
                    // Extraer número de orden (col 0)
                    const numero = cells[0]?.innerText?.trim();
                    
                    // Extraer fecha (col 1)
                    const fecha = cells[1]?.innerText?.trim().replace(/\n/g, ' ');
                    
                    // Extraer paciente (col 2) - formato: "ID E:edad S:sexo\nNOMBRE"
                    const pacienteRaw = cells[2]?.innerText?.trim();
                    const pacienteLines = pacienteRaw?.split('\n') || [];
                    const pacienteInfo = pacienteLines[0] || '';  // ID E:xx S:x
                    const pacienteNombre = pacienteLines[1] || '';  // Nombre
                    
                    // Extraer estado (col 3)
                    const estado = cells[3]?.innerText?.trim();
                    
                    // Extraer valor (col 4)
                    const valor = cells[4]?.innerText?.trim();
                    
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
                        numero_orden: numero,
                        fecha: fecha,
                        paciente_info: pacienteInfo,
                        paciente_nombre: pacienteNombre,
                        estado: estado,
                        valor: valor,
                        id_interno: idInterno
                    });
                }
                
                return ordenes;
            }
        """)
        
        # Mostrar resultados
        if len(ordenes) == 0:
            print("   ⚠️ No se encontraron órdenes para 'Chandi'")
        else:
            for i, orden in enumerate(ordenes, 1):
                print(f"\n   📦 Orden {i}:")
                print(f"      Número: {orden['numero_orden']}")
                print(f"      Fecha: {orden['fecha']}")
                print(f"      Paciente: {orden['paciente_nombre']}")
                print(f"      Info: {orden['paciente_info']}")
                print(f"      Estado: {orden['estado']}")
                print(f"      Valor: {orden['valor']}")
                print(f"      ID interno: {orden['id_interno']}")
        
        print("\n" + "=" * 60)
        print("✅ Prueba completada!")
        print("=" * 60)
        
        # Guardar resultado
        with open("test_search_result.json", "w", encoding="utf-8") as f:
            json.dump({
                "busqueda": "Chandi",
                "resultados": ordenes
            }, f, indent=2, ensure_ascii=False)
        print("\n📁 Resultado guardado en: test_search_result.json")
        
        input("\nPresiona Enter para cerrar el navegador...")
        await context.close()


if __name__ == "__main__":
    asyncio.run(test_search_and_extract())
