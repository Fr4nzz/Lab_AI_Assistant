"""
Tool Definitions - Define the tools the AI agent can use.
These are JSON-schema defined functions with short names to minimize token usage.
"""

TOOL_DEFINITIONS = [
    # ============================================================
    # DATA RETRIEVAL TOOLS (Background - keeps tab open for reuse)
    # ============================================================
    {
        "name": "get_reportes",
        "description": "Obtiene resultados de exámenes para una orden. MANTIENE LA PESTAÑA ABIERTA para ediciones posteriores.",
        "parameters": {
            "type": "object",
            "properties": {
                "orden": {
                    "type": "string",
                    "description": "Número de orden (ej: '2501181')"
                }
            },
            "required": ["orden"]
        },
        "execution_mode": "background_keep_tab"
    },
    {
        "name": "get_orden",
        "description": "Obtiene detalles de una orden (lista de exámenes, info del paciente). Usar para verificar si un examen existe antes de editar.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "ID interno de la orden"
                }
            },
            "required": ["id"]
        },
        "execution_mode": "background"
    },

    # ============================================================
    # ORDER MANAGEMENT TOOLS (Visible - user interaction needed)
    # ============================================================
    {
        "name": "create_orden",
        "description": "Crea una nueva orden. Usar cuando el paciente NO ESTÁ en la lista de órdenes recientes.",
        "parameters": {
            "type": "object",
            "properties": {
                "cedula": {
                    "type": "string",
                    "description": "Cédula del paciente"
                },
                "exams": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de códigos de exámenes a agregar (ej: ['EMO', 'BH'])"
                }
            },
            "required": ["cedula", "exams"]
        },
        "execution_mode": "visible"
    },
    {
        "name": "add_exam",
        "description": "Agrega un examen a una orden existente (navega a la página de edición).",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "ID interno de la orden"
                },
                "exam": {
                    "type": "string",
                    "description": "Código del examen a agregar"
                }
            },
            "required": ["id", "exam"]
        },
        "execution_mode": "visible"
    },

    # ============================================================
    # RESULT EDITING TOOLS (Visible - auto-highlights changes)
    # ============================================================
    {
        "name": "fill",
        "description": "Llena un campo de resultado de examen. Auto-resalta el campo modificado.",
        "parameters": {
            "type": "object",
            "properties": {
                "e": {
                    "type": "string",
                    "description": "Nombre del examen"
                },
                "f": {
                    "type": "string",
                    "description": "Nombre del campo"
                },
                "v": {
                    "type": "string",
                    "description": "Valor a ingresar"
                }
            },
            "required": ["e", "f", "v"]
        },
        "execution_mode": "visible",
        "auto_highlight": True
    },
    {
        "name": "fill_many",
        "description": "Llena múltiples campos de resultados. Auto-resalta todos los campos modificados.",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "e": {"type": "string", "description": "Nombre del examen"},
                            "f": {"type": "string", "description": "Nombre del campo"},
                            "v": {"type": "string", "description": "Valor"}
                        },
                        "required": ["e", "f", "v"]
                    },
                    "description": "Lista de campos a llenar"
                }
            },
            "required": ["data"]
        },
        "execution_mode": "visible",
        "auto_highlight": True
    },

    # ============================================================
    # UI TOOLS
    # ============================================================
    {
        "name": "hl",
        "description": "Resalta campos específicos para llamar la atención del usuario (sin editarlos).",
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Nombres de campos a resaltar"
                },
                "color": {
                    "type": "string",
                    "enum": ["yellow", "green", "red", "blue"],
                    "description": "Color del resaltado (default: yellow)"
                }
            },
            "required": ["fields"]
        },
        "execution_mode": "visible"
    },
    {
        "name": "ask_user",
        "description": "Solicita una acción del usuario (guardar, validar, proporcionar información).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["save", "validate", "info"],
                    "description": "Tipo de acción solicitada"
                },
                "msg": {
                    "type": "string",
                    "description": "Mensaje para el usuario"
                }
            },
            "required": ["action", "msg"]
        },
        "execution_mode": "visible"
    }
]

# Modos de ejecución explicados
EXECUTION_MODES = {
    "background": {
        # Abre pestaña oculta, ejecuta, cierra pestaña, retorna datos
        "headless": True,
        "keep_tab": False
    },
    "background_keep_tab": {
        # Abre pestaña (oculta inicialmente), ejecuta, MANTIENE pestaña para reusar
        # La pestaña se hace visible cuando se llama fill/fill_many
        "headless": True,
        "keep_tab": True,
        "show_on_edit": True
    },
    "visible": {
        # Usa navegador visible, el usuario ve todo
        "headless": False,
        "keep_tab": True
    }
}


def get_tools_for_gemini() -> list:
    """
    Retorna las definiciones de herramientas en formato Gemini.
    """
    tools = []
    for tool in TOOL_DEFINITIONS:
        tools.append({
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"]
        })
    return tools


def get_tools_description() -> str:
    """
    Genera una descripción textual de las herramientas para incluir en el prompt.
    """
    lines = []
    for tool in TOOL_DEFINITIONS:
        params = tool["parameters"]["properties"]
        param_list = ", ".join([
            f"{k}: {v.get('type', 'any')}"
            for k, v in params.items()
        ])
        lines.append(f"- {tool['name']}({param_list}): {tool['description']}")
    return "\n".join(lines)
