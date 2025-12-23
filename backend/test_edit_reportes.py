"""
Script para EDITAR valores en la página de reportes.
Modifica campos específicos y resalta visualmente los cambios.
Guarda el HTML completo (antes y después) para análisis offline por Claude Code.
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright

# Ruta del browser_data
SCRIPT_DIR = Path(__file__).parent.absolute()
BROWSER_DATA_DIR = SCRIPT_DIR / "browser_data"
HTML_SAMPLES_DIR = SCRIPT_DIR / "html_samples"

# Orden a editar
NUMERO_ORDEN = "2501181"


async def save_page_html(page, prefix: str, numero_orden: str, suffix: str = ""):
    """Guarda el HTML completo de la página para análisis offline."""
    HTML_SAMPLES_DIR.mkdir(exist_ok=True)

    # Obtener el HTML completo
    html_content = await page.content()

    # Crear nombre de archivo con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix_part = f"_{suffix}" if suffix else ""
    filename = f"{prefix}_{numero_orden}{suffix_part}_{timestamp}.html"
    filepath = HTML_SAMPLES_DIR / filename

    # Guardar el archivo
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n💾 HTML guardado en: {filepath}")
    print(f"   Tamaño: {len(html_content):,} bytes")

    return filepath

# Cambios a realizar
CAMBIOS = [
    {"campo": "Hemoglobina", "nuevo_valor": "15.5"},
    {"campo": "Glóbulos Blancos", "nuevo_valor": "8.2"},
]


async def edit_reportes():
    """Editar valores en la página de reportes y resaltar cambios."""
    
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
        await page.wait_for_timeout(2000)  # Esperar renderizado Vue.js

        print(f"   URL: {page.url}")

        # Guardar HTML ANTES de los cambios
        await save_page_html(page, "reportes_edit", NUMERO_ORDEN, "before")
        
        # 2. Inyectar estilos CSS para resaltar cambios
        print("\n🎨 Inyectando estilos para resaltar cambios...")
        await page.evaluate("""
            () => {
                const style = document.createElement('style');
                style.id = 'ai-highlight-styles';
                style.textContent = `
                    .ai-modified {
                        background-color: #fef3c7 !important;
                        border: 2px solid #f59e0b !important;
                        box-shadow: 0 0 10px rgba(245, 158, 11, 0.5) !important;
                        transition: all 0.3s ease !important;
                    }
                    .ai-modified-row {
                        background-color: #fffbeb !important;
                    }
                    .ai-modified-label {
                        position: relative;
                    }
                    .ai-modified-label::after {
                        content: '✏️ MODIFICADO';
                        position: absolute;
                        right: -100px;
                        top: 50%;
                        transform: translateY(-50%);
                        background: #f59e0b;
                        color: white;
                        padding: 2px 8px;
                        border-radius: 4px;
                        font-size: 10px;
                        font-weight: bold;
                        white-space: nowrap;
                    }
                    .ai-change-indicator {
                        display: inline-block;
                        background: #ef4444;
                        color: white;
                        padding: 2px 6px;
                        border-radius: 4px;
                        font-size: 11px;
                        margin-left: 10px;
                        animation: pulse 1s infinite;
                    }
                    @keyframes pulse {
                        0%, 100% { opacity: 1; }
                        50% { opacity: 0.7; }
                    }
                `;
                document.head.appendChild(style);
            }
        """)
        
        # 3. Realizar los cambios
        print("\n" + "="*70)
        print("📝 REALIZANDO CAMBIOS:")
        print("-"*70)
        
        cambios_realizados = []
        
        for cambio in CAMBIOS:
            campo = cambio["campo"]
            nuevo_valor = cambio["nuevo_valor"]
            
            print(f"\n   🔄 Buscando campo: '{campo}'...")
            
            # Buscar el campo y modificarlo
            resultado = await page.evaluate("""
                (params) => {
                    const { campo, nuevoValor } = params;
                    
                    // Buscar todas las filas de parámetros
                    const rows = document.querySelectorAll('tr.parametro');
                    
                    for (const row of rows) {
                        const labelCell = row.querySelector('td:first-child');
                        const labelText = labelCell?.innerText?.trim();
                        
                        // Verificar si el nombre del campo coincide
                        if (labelText && labelText.includes(campo)) {
                            const input = row.querySelector('input');
                            
                            if (input) {
                                const valorAnterior = input.value;
                                
                                // Cambiar el valor
                                input.value = nuevoValor;
                                
                                // Disparar eventos para que Vue.js detecte el cambio
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                                input.dispatchEvent(new Event('change', { bubbles: true }));
                                input.dispatchEvent(new Event('blur', { bubbles: true }));
                                
                                // Resaltar el input
                                input.classList.add('ai-modified');
                                
                                // Resaltar la fila
                                row.classList.add('ai-modified-row');
                                
                                // Agregar indicador de cambio
                                const indicator = document.createElement('span');
                                indicator.className = 'ai-change-indicator';
                                indicator.textContent = `${valorAnterior} → ${nuevoValor}`;
                                
                                // Insertar después del input
                                input.parentNode.appendChild(indicator);
                                
                                return {
                                    success: true,
                                    campo: labelText,
                                    valorAnterior: valorAnterior,
                                    valorNuevo: nuevoValor
                                };
                            }
                        }
                    }
                    
                    return {
                        success: false,
                        error: `Campo '${campo}' no encontrado`
                    };
                }
            """, {"campo": campo, "nuevoValor": nuevo_valor})
            
            if resultado["success"]:
                print(f"      ✅ Campo: {resultado['campo']}")
                print(f"         Valor anterior: {resultado['valorAnterior']}")
                print(f"         Valor nuevo: {resultado['valorNuevo']}")
                cambios_realizados.append(resultado)
            else:
                print(f"      ❌ Error: {resultado.get('error', 'Desconocido')}")
        
        # 4. Scroll hasta el primer cambio para mostrarlo
        if cambios_realizados:
            print("\n📍 Haciendo scroll al primer campo modificado...")
            await page.evaluate("""
                () => {
                    const modified = document.querySelector('.ai-modified');
                    if (modified) {
                        modified.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }
            """)
        
        # 5. Resumen
        print("\n" + "="*70)
        print("📊 RESUMEN DE CAMBIOS:")
        print("-"*70)
        print(f"   Total cambios solicitados: {len(CAMBIOS)}")
        print(f"   Cambios realizados: {len(cambios_realizados)}")
        print(f"   Cambios fallidos: {len(CAMBIOS) - len(cambios_realizados)}")
        
        if cambios_realizados:
            print("\n   📋 Detalle de cambios:")
            for c in cambios_realizados:
                print(f"      • {c['campo']}: {c['valorAnterior']} → {c['valorNuevo']}")
        
        print("\n" + "="*70)
        print("⚠️  IMPORTANTE:")
        print("   - Los cambios están resaltados en AMARILLO en el navegador")
        print("   - Los valores anteriores se muestran junto a los nuevos")
        print("   - DEBES hacer click en 'Guardar' manualmente para confirmar")
        print("="*70)
        
        # Guardar log de cambios
        with open("cambios_realizados.json", "w", encoding="utf-8") as f:
            json.dump({
                "numero_orden": NUMERO_ORDEN,
                "cambios_solicitados": CAMBIOS,
                "cambios_realizados": cambios_realizados
            }, f, indent=2, ensure_ascii=False)

        print("\n📁 Log guardado en: cambios_realizados.json")

        # Guardar HTML DESPUÉS de los cambios
        await save_page_html(page, "reportes_edit", NUMERO_ORDEN, "after")

        input("\n👀 Revisa los cambios en el navegador. Presiona Enter para cerrar...")
        await context.close()


if __name__ == "__main__":
    asyncio.run(edit_reportes())
