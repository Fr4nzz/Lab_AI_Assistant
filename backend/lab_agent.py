"""Lab Agent - The brain that coordinates Gemini AI with browser control."""
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from gemini_handler import GeminiHandler, create_image_part, create_audio_part
from browser_manager import BrowserManager
from database import Database


# System prompt for Gemini
SYSTEM_PROMPT = """Eres un asistente de laboratorio clínico experto. Tu trabajo es ayudar a ingresar resultados de exámenes en el sistema laboratoriofranz.orion-labs.com.

## Tus capacidades:
1. Interpretar texto, imágenes de cuadernos manuscritos, y audio
2. Navegar el sitio web del laboratorio
3. Extraer y verificar información de pacientes y órdenes
4. Preparar planes de acción para ingresar resultados

## Reglas importantes:
1. NUNCA hagas click en botones de "Guardar", "Save", "Eliminar" o "Delete" - el usuario lo hará manualmente
2. Siempre presenta un plan para que el usuario lo revise antes de ejecutar
3. Si no tienes suficiente información, explora el sitio primero
4. Verifica que los pacientes y órdenes existan antes de intentar agregar resultados

## Conocimiento del sitio:
- /ordenes - Lista de órdenes recientes
- /ordenes/create - Crear nueva orden
- /ordenes/{id}/edit - Editar orden existente
- /reportes2?numeroOrden={id} - Página de resultados para ingresar valores

## Interpretación de abreviaturas manuscritas:
### EMO (Elemental y Microscópico de Orina):
- Color: AM/A = Amarillo, AP = Amarillo Claro, AI = Amarillo Intenso
- Aspecto: TP = Transparente, LT = Ligeramente Turbio, T = Turbio
- Leucocitos: 10-25 = +, 75 = ++, 500 = +++
- Proteínas: TRZ = Trazas, valores en mg/dL
- pH: valores numéricos (5.0, 6.0, 7.0, etc.)

### Coproparasitario:
- Consistencia: D = Dura, B = Blanda, S = Semiblanda, L = Líquida
- Si no hay parásitos: seleccionar "No se observan parásitos"

## Formato de respuesta:
SIEMPRE responde en JSON con esta estructura:

Para exploración (cuando necesitas más información):
{
    "mode": "exploration",
    "reasoning": "Explicación de por qué necesito explorar",
    "actions": [
        {"action": "navigate", "url": "..."},
        {"action": "click", "element_index": N},
        {"action": "scroll", "direction": "down", "amount": 500}
    ]
}

Para hacer una pregunta al usuario:
{
    "mode": "question",
    "question": "Tu pregunta aquí",
    "options": ["Opción 1", "Opción 2"]  // opcional
}

Para presentar un plan de acción:
{
    "mode": "plan",
    "understanding": "Resumen de lo que entendí que el usuario quiere hacer",
    "extracted_data": [
        {
            "patient": "Nombre del paciente",
            "exam": "Nombre del examen",
            "fields": [
                {"field": "Campo", "value": "Valor", "unit": "unidad opcional"}
            ]
        }
    ],
    "steps": [
        {"action": "navigate", "url": "...", "description": "Descripción para el usuario"},
        {"action": "type", "element_index": N, "text": "...", "description": "..."}
    ],
    "suggestions": [
        {"type": "correction", "message": "Vi X pero parece Y, ¿corrijo?", "apply": false}
    ]
}

## Estado actual del navegador:
{browser_state}

## Historial de la conversación:
{chat_history}

## Mensaje del usuario:
{user_message}
"""


class LabAgent:
    """Coordinates Gemini AI with browser control for lab result entry."""
    
    def __init__(
        self,
        gemini_handler: GeminiHandler,
        browser_manager: BrowserManager,
        database: Database,
        site_knowledge_dir: str = "./site_knowledge"
    ):
        self.gemini = gemini_handler
        self.browser = browser_manager
        self.db = database
        self.site_knowledge = self._load_site_knowledge(site_knowledge_dir)
        self.max_exploration_steps = 5  # Prevent infinite exploration loops
    
    def _load_site_knowledge(self, directory: str) -> Dict:
        """Load site knowledge JSON files."""
        knowledge = {}
        path = Path(directory)
        if path.exists():
            for json_file in path.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        knowledge[json_file.stem] = json.load(f)
                except Exception as e:
                    print(f"Warning: Could not load {json_file}: {e}")
        return knowledge
    
    async def process_message(
        self,
        chat_id: str,
        message: str,
        attachments: List[Dict] = None,
        exploration_depth: int = 0
    ) -> Dict[str, Any]:
        """
        Process a user message and return the appropriate response.
        
        Args:
            chat_id: The chat session ID
            message: User's text message
            attachments: List of attachments [{type: "image/audio", data: base64, mime_type: ...}]
            exploration_depth: Current exploration depth (to prevent infinite loops)
        
        Returns:
            Response dict with mode and relevant data
        """
        # Get chat history
        history = self.db.get_messages(chat_id, limit=20)
        
        # Get browser state
        browser_state = await self.browser.get_state()
        
        # Build the prompt
        prompt = self._build_prompt(message, history, browser_state)
        
        # Build contents for Gemini (text + attachments)
        contents = [prompt]
        
        if attachments:
            for attachment in attachments:
                if attachment["type"].startswith("image"):
                    contents.append(create_image_part(
                        attachment["data"],
                        attachment.get("mime_type", "image/jpeg")
                    ))
                elif attachment["type"].startswith("audio"):
                    contents.append(create_audio_part(
                        attachment["data"],
                        attachment.get("mime_type", "audio/wav")
                    ))
        
        # Call Gemini
        response_text, success = await self.gemini.send_request(
            system_prompt=SYSTEM_PROMPT.replace("{browser_state}", json.dumps(browser_state, ensure_ascii=False))
                                       .replace("{chat_history}", self._format_history(history))
                                       .replace("{user_message}", message),
            contents=contents
        )
        
        if not success:
            return {
                "mode": "error",
                "error": response_text
            }
        
        # Parse Gemini's response
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            return {
                "mode": "error",
                "error": f"Failed to parse Gemini response: {e}\nRaw: {response_text[:500]}"
            }
        
        mode = response_data.get("mode")
        
        if mode == "exploration":
            # Execute exploration actions and recurse
            if exploration_depth >= self.max_exploration_steps:
                return {
                    "mode": "error",
                    "error": "Maximum exploration depth reached. Please provide more specific instructions."
                }
            
            actions = response_data.get("actions", [])
            for action in actions:
                result = await self.browser.execute_action(action)
                if not result.get("success"):
                    break
            
            # Recurse with new browser state
            return await self.process_message(
                chat_id=chat_id,
                message="",  # Empty message, just processing new state
                attachments=None,
                exploration_depth=exploration_depth + 1
            )
        
        elif mode == "question":
            # Save assistant message and return question
            self.db.add_message(chat_id, "assistant", response_data.get("question", ""))
            return {
                "mode": "question",
                "question": response_data.get("question"),
                "options": response_data.get("options")
            }
        
        elif mode == "plan":
            # Save the plan and return for user review
            plan = {
                "understanding": response_data.get("understanding"),
                "extracted_data": response_data.get("extracted_data", []),
                "steps": response_data.get("steps", []),
                "suggestions": response_data.get("suggestions", [])
            }
            
            self.db.save_plan(chat_id, plan)
            self.db.add_message(chat_id, "assistant", response_data.get("understanding", ""))
            
            return {
                "mode": "plan",
                **plan
            }
        
        else:
            return {
                "mode": "error",
                "error": f"Unknown response mode: {mode}"
            }
    
    def _build_prompt(self, message: str, history: List[Dict], browser_state: Dict) -> str:
        """Build the prompt for Gemini."""
        parts = []
        
        if message:
            parts.append(f"Mensaje del usuario: {message}")
        
        parts.append(f"\nEstado actual del navegador:")
        parts.append(f"- URL: {browser_state.get('url', 'N/A')}")
        parts.append(f"- Título: {browser_state.get('title', 'N/A')}")
        parts.append(f"- Elementos interactivos: {len(browser_state.get('elements', []))} elementos")
        
        # Add condensed element list
        elements = browser_state.get("elements", [])[:30]  # Limit to first 30
        if elements:
            parts.append("\nElementos disponibles (primeros 30):")
            for el in elements:
                el_desc = f"[{el['index']}] <{el['tag']}>"
                if el.get('text'):
                    el_desc += f" '{el['text'][:50]}'"
                if el.get('placeholder'):
                    el_desc += f" placeholder='{el['placeholder']}'"
                if el.get('type'):
                    el_desc += f" type={el['type']}"
                parts.append(el_desc)
        
        return "\n".join(parts)
    
    def _format_history(self, history: List[Dict]) -> str:
        """Format chat history for the prompt."""
        if not history:
            return "No hay mensajes previos."
        
        formatted = []
        for msg in history[-10:]:  # Last 10 messages
            role = "Usuario" if msg["role"] == "user" else "Asistente"
            content = msg["content"][:200]  # Truncate long messages
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)
    
    async def execute_plan(self, plan: Dict) -> Dict[str, Any]:
        """
        Execute an approved plan.
        
        Args:
            plan: The plan dict with steps to execute
        
        Returns:
            Execution result
        """
        steps = plan.get("steps", [])
        results = []
        
        for i, step in enumerate(steps):
            # Skip forbidden actions (extra safety)
            if self.browser.is_action_forbidden(step):
                results.append({
                    "step": i,
                    "action": step.get("action"),
                    "success": False,
                    "error": "Action skipped: involves save/delete"
                })
                continue
            
            result = await self.browser.execute_action(step)
            results.append({
                "step": i,
                "action": step.get("action"),
                "description": step.get("description", ""),
                **result
            })
            
            if not result.get("success"):
                break
        
        all_success = all(r.get("success", False) for r in results)
        
        return {
            "success": all_success,
            "results": results,
            "message": "Campos llenados. Por favor haz click en 'Guardar' en el navegador." if all_success else "Algunas acciones fallaron. Revisa el navegador."
        }
    
    async def get_orders_summary(self) -> Dict[str, Any]:
        """Get a summary of recent orders from the orders page."""
        await self.browser.navigate(f"{self.browser.page.url.split('/')[0]}//{self.browser.page.url.split('/')[2]}/ordenes")
        
        # Extract order information from the page
        orders_data = await self.browser.page.evaluate("""
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                const orders = [];
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length > 0) {
                        orders.push({
                            number: cells[0]?.innerText?.trim(),
                            patient: cells[1]?.innerText?.trim(),
                            date: cells[2]?.innerText?.trim(),
                            status: cells[3]?.innerText?.trim()
                        });
                    }
                });
                return orders.slice(0, 20);  // Last 20 orders
            }
        """)
        
        return {
            "url": self.browser.page.url,
            "orders": orders_data
        }
