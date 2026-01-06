"""Tool name translations for user-friendly display."""

# Map internal tool names to user-friendly Spanish labels
TOOL_TRANSLATIONS = {
    # Browser tools
    "get_page_content": "📄 Leyendo página",
    "click_element": "👆 Haciendo clic",
    "fill_input": "✍️ Escribiendo",
    "navigate": "🌐 Navegando",
    "get_screenshot": "📸 Capturando pantalla",
    "scroll_page": "📜 Desplazando página",
    "wait_for_element": "⏳ Esperando elemento",
    "extract_table": "📊 Extrayendo tabla",

    # Lab tools
    "create_order": "📋 Creando orden",
    "create_new_order": "📋 Creando orden nueva",
    "search_patient": "🔍 Buscando paciente",
    "get_patient_info": "👤 Obteniendo info paciente",
    "add_exam": "🧪 Agregando examen",
    "remove_exam": "❌ Removiendo examen",
    "get_order_summary": "📝 Obteniendo resumen",
    "confirm_order": "✅ Confirmando orden",
    "search_orders": "🔍 Buscando órdenes",
    "get_order_results": "📋 Obteniendo resultados",
    "get_order_info": "ℹ️ Info de orden",
    "edit_results": "✏️ Editando resultados",
    "edit_order_exams": "📝 Editando exámenes",
    "get_available_exams": "📋 Exámenes disponibles",
    "ask_user": "❓ Pregunta al usuario",

    # General tools
    "search": "🔎 Buscando",
    "calculate": "🧮 Calculando",
    "format_text": "📝 Formateando texto",

    # Image preprocessing tools
    "image-rotation": "🔄 Corrigiendo rotación",
    "document-segmentation": "📐 Detectando documento",
}


def get_tool_display_name(tool_name: str) -> str:
    """Get user-friendly display name for a tool.

    Args:
        tool_name: Internal tool name (e.g., "get_page_content")

    Returns:
        User-friendly name with emoji (e.g., "📄 Leyendo página")
    """
    if tool_name in TOOL_TRANSLATIONS:
        return TOOL_TRANSLATIONS[tool_name]
    # Fallback: replace underscores with spaces for readability
    friendly_name = tool_name.replace("_", " ")
    return f"🔧 {friendly_name}"
