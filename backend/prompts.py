"""
System prompts for the LangGraph agent.

Loads prompts from config/prompts.yaml for easy editing via the web UI.
Falls back to hardcoded defaults if the file is missing.
"""
import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Path to prompts config file
PROMPTS_FILE = Path(__file__).parent / "config" / "prompts.yaml"

# Cache for loaded prompts
_prompts_cache: Optional[dict] = None


def load_prompts() -> dict:
    """
    Load prompts from YAML config file.
    Returns cached version if already loaded.
    """
    global _prompts_cache

    if _prompts_cache is not None:
        return _prompts_cache

    try:
        if PROMPTS_FILE.exists():
            with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
                _prompts_cache = yaml.safe_load(f)
                logger.info(f"[Prompts] Loaded from {PROMPTS_FILE.name}")
                return _prompts_cache
    except Exception as e:
        logger.warning(f"[Prompts] Failed to load from YAML: {e}")

    # Fallback to defaults
    _prompts_cache = get_default_prompts()
    logger.info("[Prompts] Using default prompts")
    return _prompts_cache


def reload_prompts() -> dict:
    """
    Force reload prompts from file (clears cache).
    Call this after updating the YAML file.
    """
    global _prompts_cache
    _prompts_cache = None
    return load_prompts()


def save_prompts(prompts: dict) -> bool:
    """
    Save prompts to YAML config file.
    Returns True on success, False on failure.
    """
    global _prompts_cache

    try:
        # Ensure directory exists
        PROMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(
                prompts,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=1000  # Prevent line wrapping
            )

        # Update cache
        _prompts_cache = prompts
        logger.info(f"[Prompts] Saved to {PROMPTS_FILE.name}")
        return True

    except Exception as e:
        logger.error(f"[Prompts] Failed to save: {e}")
        return False


def get_default_prompts() -> dict:
    """Return default prompts if config file is missing."""
    return {
        "system_prompt": """Asistente de laboratorio clínico para Orion Labs.

## ROL
- Ingresa resultados interpretando texto, imágenes manuscritas y audio
- Interpreta imágenes con máxima precisión - vidas dependen de ello
- USA herramientas para actuar, nunca solo describas

## EFICIENCIA (CRÍTICO)
- Operaciones en lote: get_order_results/edit_results con TODAS las órdenes a la vez
- Solo edita campos que necesiten cambio
- Después de edit_results → responde directamente, sin más herramientas

## COTIZACIÓN
Para precios: create_new_order(cedula="", exams=["CODIGO1",...])
Usa códigos EXACTOS del CONTEXTO.

## EDITAR ÓRDENES EXISTENTES
Para modificar una orden abierta (nueva o guardada):
- edit_order_exams(tab_index=N, cedula="...", add=["..."], remove=["..."])
- Usa tab_index del CONTEXTO para órdenes nuevas (sin ID aún)
- Usa order_id para órdenes guardadas
- Puedes actualizar cedula en órdenes nuevas sin recrearlas

## SEGURIDAD
Herramientas LLENAN formularios, NO guardan.
SIEMPRE termina con: "Haz click en Guardar para confirmar."
""",
        "abbreviations": """## ABREVIATURAS
EMO: AM=Amarillo, AP=Amarillo Claro, TP=Transparente, LT=Lig.Turbio, NEG=Negativo, ESC=Escasas, MOD=Moderadas
Copro: D=Dura, B=Blanda, S=Semiblanda, C=Café, CA=Café Amarillento, NSO=No se observan parásitos
BH: valores numéricos directos (Hb 15.5, Hto 46)
""",
        "image_interpretation": """## INTERPRETACIÓN DE IMÁGENES
Al recibir imágenes de resultados de laboratorio:

1. **Identificación del paciente**: Busca nombre, cédula, fecha en la parte superior
2. **Tipo de examen**: Identifica si es BH, EMO, Copro, Química, etc.
3. **Valores**: Lee cada valor con cuidado, prestando atención a:
   - Números decimales (15.5 vs 155)
   - Unidades de medida
   - Valores de referencia si están presentes
4. **Escritura manuscrita**:
   - Números: 1 vs 7, 0 vs O, 5 vs S
   - Si hay duda, prefiere el valor clínicamente probable
5. **Orientación**: Si la imagen está rotada, interpreta correctamente la orientación
""",
        "welcome_message": """Hola! Soy tu asistente de laboratorio.

Puedo ayudarte a:
- Buscar ordenes por paciente o cedula
- Ingresar resultados de multiples examenes a la vez
- Agregar examenes a ordenes existentes
- Crear nuevas ordenes

Solo lleno los formularios - tu haces click en "Guardar" para confirmar.

Que resultados necesitas ingresar?"""
    }


def get_system_prompt() -> str:
    """Get the complete system prompt with all sections."""
    prompts = load_prompts()

    parts = [prompts.get("system_prompt", "").strip()]

    # Add abbreviations
    abbrev = prompts.get("abbreviations", "").strip()
    if abbrev:
        parts.append(abbrev)

    # Add image interpretation instructions
    image_inst = prompts.get("image_interpretation", "").strip()
    if image_inst:
        parts.append(image_inst)

    return "\n\n".join(parts)


def get_welcome_message() -> str:
    """Get the welcome message for new conversations."""
    prompts = load_prompts()
    return prompts.get("welcome_message", "").strip()


# For backwards compatibility with old code
def build_system_prompt(tools_description: str, current_context: str, chat_history: str) -> str:
    """
    Build the complete system prompt with current context.
    This function is kept for backwards compatibility.
    """
    return get_system_prompt() + f"\n\nCONTEXTO ACTUAL:\n{current_context}"


# Make SYSTEM_PROMPT and WELCOME_MESSAGE work as simple strings
# by using module-level __getattr__
def __getattr__(name):
    if name == "SYSTEM_PROMPT":
        return get_system_prompt()
    elif name == "WELCOME_MESSAGE":
        return get_welcome_message()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
