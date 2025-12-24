"""
JSON Schemas - Define the JSON schema for AI responses.
The AI must ALWAYS respond in this format.
"""

# Esquema de respuesta del AI
AI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "Mensaje para mostrar al usuario en el chat (en español)"
        },
        "tool_calls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "parameters": {"type": "object"}
                },
                "required": ["tool", "parameters"]
            },
            "description": "Lista de herramientas a ejecutar en secuencia"
        },
        "data_to_review": {
            "type": "object",
            "properties": {
                "patient": {"type": "string"},
                "exam": {"type": "string"},
                "changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "f": {"type": "string", "description": "Nombre del campo"},
                            "v": {"type": "string", "description": "Nuevo valor"},
                            "prev": {"type": "string", "description": "Valor anterior"}
                        }
                    }
                }
            },
            "description": "Datos para que el usuario revise antes de guardar"
        },
        "status": {
            "type": "string",
            "enum": ["executing", "waiting_for_user", "completed", "error"],
            "description": "Estado actual de la operación"
        },
        "next_step": {
            "type": "string",
            "description": "Qué pasará después (opcional)"
        }
    },
    "required": ["message", "status"]
}


# Esquema para datos de órdenes
ORDEN_SCHEMA = {
    "type": "object",
    "properties": {
        "num": {"type": "string", "description": "Número de orden"},
        "fecha": {"type": "string", "description": "Fecha de la orden"},
        "cedula": {"type": "string", "description": "Cédula del paciente"},
        "paciente": {"type": "string", "description": "Nombre del paciente"},
        "sexo": {"type": "string", "enum": ["M", "F"]},
        "edad": {"type": "string"},
        "estado": {"type": "string"},
        "valor": {"type": "string"},
        "id": {"type": "integer", "description": "ID interno de la orden"}
    }
}


# Esquema para campos de exámenes
CAMPO_EXAMEN_SCHEMA = {
    "type": "object",
    "properties": {
        "f": {"type": "string", "description": "Nombre del campo"},
        "tipo": {"type": "string", "enum": ["input", "select"]},
        "val": {"type": "string", "description": "Valor actual"},
        "ref": {"type": "string", "description": "Valor de referencia"},
        "opciones": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Opciones disponibles (solo para select)"
        }
    }
}


# Esquema para exámenes
EXAMEN_SCHEMA = {
    "type": "object",
    "properties": {
        "nombre": {"type": "string"},
        "estado": {"type": "string"},
        "tipo_muestra": {"type": "string"},
        "campos": {
            "type": "array",
            "items": CAMPO_EXAMEN_SCHEMA
        }
    }
}


def validate_ai_response(response: dict) -> tuple[bool, str]:
    """
    Valida que la respuesta del AI cumpla con el esquema.

    Returns:
        (is_valid, error_message)
    """
    # Verificar campos requeridos
    if "message" not in response:
        return False, "Missing required field: message"

    if "status" not in response:
        return False, "Missing required field: status"

    # Verificar que status sea válido
    valid_statuses = ["executing", "waiting_for_user", "completed", "error"]
    if response["status"] not in valid_statuses:
        return False, f"Invalid status: {response['status']}. Must be one of {valid_statuses}"

    # Verificar tool_calls si existe
    if "tool_calls" in response:
        if not isinstance(response["tool_calls"], list):
            return False, "tool_calls must be an array"

        for i, call in enumerate(response["tool_calls"]):
            if "tool" not in call:
                return False, f"tool_calls[{i}] missing 'tool' field"
            if "parameters" not in call:
                return False, f"tool_calls[{i}] missing 'parameters' field"

    return True, ""
