"""
Tool Definitions - Define the tools the AI agent can use.
"""

TOOL_DEFINITIONS = [
    # ============================================================
    # DATA RETRIEVAL TOOLS
    # ============================================================
    {
        "name": "search_orders",
        "description": "Busca órdenes por nombre de paciente o cédula.",
        "parameters": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Texto para buscar (nombre o cédula)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Máximo de órdenes a obtener (default: 10)"
                }
            },
            "required": []
        },
        "execution_mode": "background"
    },
    {
        "name": "get_exam_fields",
        "description": "Obtiene campos de exámenes para editar. SIEMPRE usa parámetro 'ordenes' (array).",
        "parameters": {
            "type": "object",
            "properties": {
                "ordenes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "REQUERIDO: Array de números de orden (campo 'num'). Ejemplo: [\"2501181\"] o [\"2501181\", \"25011314\"]"
                }
            },
            "required": ["ordenes"]
        },
        "execution_mode": "background_keep_tab"
    },
    {
        "name": "get_order_details",
        "description": "Obtiene detalles de una orden (exámenes, paciente). Usa 'id' interno.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "ID interno de la orden (ej: 4282)"
                }
            },
            "required": ["id"]
        },
        "execution_mode": "background"
    },

    # ============================================================
    # ORDER MANAGEMENT TOOLS
    # ============================================================
    {
        "name": "create_order",
        "description": "Crea una nueva orden con paciente y exámenes.",
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
                    "description": "Lista de códigos de exámenes (ej: ['EMO', 'BH'])"
                }
            },
            "required": ["cedula", "exams"]
        },
        "execution_mode": "visible"
    },
    {
        "name": "add_exam",
        "description": "Agrega un examen a una orden existente. Usa 'id' interno.",
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
    # RESULT EDITING TOOLS
    # ============================================================
    {
        "name": "edit_results",
        "description": "Edita campos de resultados en una o más órdenes. Auto-resalta cambios.",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "orden": {"type": "string", "description": "Número de orden (campo 'num')"},
                            "e": {"type": "string", "description": "Nombre del examen"},
                            "f": {"type": "string", "description": "Nombre del campo"},
                            "v": {"type": "string", "description": "Valor"}
                        },
                        "required": ["orden", "e", "f", "v"]
                    },
                    "description": "Lista de campos: [{orden, e (examen), f (campo), v (valor)}]"
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
        "name": "highlight",
        "description": "Resalta campos sin editarlos (para llamar atención del usuario).",
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
        "description": "Solicita una acción del usuario (guardar, validar, info).",
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
