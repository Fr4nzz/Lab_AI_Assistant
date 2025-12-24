"""
Lab Agent - Main AI agent that orchestrates everything.
Coordinates Gemini AI with browser control for lab result entry.
"""
import json
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from gemini_handler import GeminiHandler, create_image_part, create_audio_part
from browser_manager import BrowserManager
from database import Database
from extractors import PageDataExtractor
from tool_executor import ToolExecutor
from tools import get_tools_description
from prompts import build_system_prompt, WELCOME_MESSAGE
from schemas import validate_ai_response
from context_formatters import (
    format_ordenes_context,
    format_reportes_context,
    format_orden_edit_context
)


# Debug configuration
DEBUG = True


def debug_print(category: str, message: str, data: Any = None):
    """Print debug info with category."""
    if not DEBUG:
        return

    prefix = f"[{category}]"
    print(f"\n{'='*60}")
    print(f"{prefix} {message}")
    if data is not None:
        if isinstance(data, str):
            # Truncate long strings
            if len(data) > 500:
                print(f"{data[:500]}...")
                print(f"  ... ({len(data)} chars total)")
            else:
                print(data)
        elif isinstance(data, dict):
            print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])
        else:
            print(str(data)[:500])
    print('='*60)


class LabAgent:
    """Main AI agent that orchestrates everything."""

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
        self.extractor: Optional[PageDataExtractor] = None
        self.executor: Optional[ToolExecutor] = None
        self.site_knowledge = self._load_site_knowledge(site_knowledge_dir)

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

    async def initialize(self):
        """Initialize extractors and executor after browser is started."""
        if self.browser.page:
            self.extractor = PageDataExtractor(self.browser.page)
            self.executor = ToolExecutor(self.browser)

    async def process_message(
        self,
        chat_id: str,
        message: str,
        attachments: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process user message and return AI response.
        Implements agentic loop: continues until AI responds without tool calls.

        Args:
            chat_id: The chat session ID
            message: User's text message
            attachments: List of attachments [{type: "image/audio", data: base64, mime_type: ...}]

        Returns:
            AI response with message, tool_calls, status, etc.
        """
        start_time = time.time()
        debug_print("REQUEST", f"Processing message for chat {chat_id[:8]}...", message)

        # Ensure initialized
        if not self.extractor:
            debug_print("INIT", "Initializing extractor and executor...")
            await self.initialize()

        # Save user message to database
        self.db.add_message(chat_id, "user", message)

        # Agentic loop - continue until AI responds without tool calls
        MAX_ITERATIONS = 5
        iteration = 0
        all_tool_results = []
        final_response = None

        while iteration < MAX_ITERATIONS:
            iteration += 1
            debug_print("LOOP", f"Iteration {iteration}/{MAX_ITERATIONS}")

            # 1. Get chat history
            history = self.db.get_messages(chat_id, limit=20)
            debug_print("HISTORY", f"Loaded {len(history)} messages from history")

            # 2. Get current page context
            debug_print("CONTEXT", "Extracting page context...")
            page_context = await self._get_current_context()
            debug_print("CONTEXT", f"Page type: {page_context.get('page_type', 'unknown')}",
                       page_context.get("formatted", "No formatted context"))

            # 3. Build prompt with tool results if any
            tool_results_context = ""
            if all_tool_results:
                tool_results_context = "\n\n## RESULTADOS DE HERRAMIENTAS EJECUTADAS\n"
                for tr in all_tool_results:
                    tool_results_context += f"### {tr['tool']}\n```json\n{json.dumps(tr['result'], ensure_ascii=False, indent=2)}\n```\n"

            system_prompt = build_system_prompt(
                tools_description=get_tools_description(),
                current_context=page_context.get("formatted", json.dumps(page_context, ensure_ascii=False)) + tool_results_context,
                chat_history=self._format_history(history)
            )
            debug_print("PROMPT", f"System prompt built ({len(system_prompt)} chars)",
                       f"First 300 chars:\n{system_prompt[:300]}")

            # 4. Build content list (text + images + audio) - only on first iteration
            if iteration == 1:
                contents = [message] if message else ["Analiza el contexto actual."]
                attachment_count = 0

                if attachments:
                    for attachment in attachments:
                        if attachment["type"].startswith("image"):
                            contents.append(create_image_part(
                                attachment["data"],
                                attachment.get("mime_type", "image/jpeg")
                            ))
                            attachment_count += 1
                        elif attachment["type"].startswith("audio"):
                            contents.append(create_audio_part(
                                attachment["data"],
                                attachment.get("mime_type", "audio/wav")
                            ))
                            attachment_count += 1
                debug_print("SEND", f"Sending to Gemini: {len(contents)} content parts, {attachment_count if iteration == 1 else 0} attachments")
            else:
                # On subsequent iterations, ask AI to continue with tool results
                contents = ["Continúa con los resultados de las herramientas ejecutadas. Proporciona la respuesta final al usuario."]
                debug_print("SEND", "Sending continuation request to Gemini")

            # 5. Call Gemini
            gemini_start = time.time()
            response_text, success = await self.gemini.send_request(
                system_prompt=system_prompt,
                contents=contents
            )
            gemini_time = time.time() - gemini_start

            debug_print("GEMINI", f"Response received in {gemini_time:.2f}s, success={success}",
                       response_text[:500] if response_text else "No response")

            if not success:
                error_response = {
                    "status": "error",
                    "message": f"Error al comunicarse con Gemini: {response_text}"
                }
                debug_print("ERROR", "Gemini request failed", error_response)
                return error_response

            # 6. Parse AI response
            try:
                ai_response = json.loads(response_text)
                debug_print("PARSE", "JSON parsed successfully", ai_response)
            except json.JSONDecodeError as e:
                error_response = {
                    "status": "error",
                    "message": f"Error al parsear respuesta del AI: {e}\nRespuesta: {response_text[:500]}"
                }
                debug_print("ERROR", f"JSON parse failed: {e}", response_text[:500])
                return error_response

            # 7. Validate response
            is_valid, error = validate_ai_response(ai_response)
            if not is_valid:
                error_response = {
                    "status": "error",
                    "message": f"Respuesta inválida del AI: {error}"
                }
                debug_print("ERROR", f"Validation failed: {error}", ai_response)
                return error_response

            debug_print("VALID", "Response validated successfully")

            # 8. Execute tool calls if any
            tool_calls = ai_response.get("tool_calls", [])
            if tool_calls:
                debug_print("TOOLS", f"Executing {len(tool_calls)} tool calls")
                for call in tool_calls:
                    debug_print("TOOL", f"Executing: {call['tool']}", call.get('parameters'))
                    result = await self.executor.execute(call["tool"], call["parameters"])
                    all_tool_results.append({
                        "tool": call["tool"],
                        "result": result
                    })
                    debug_print("TOOL_RESULT", f"{call['tool']} completed", result)

                # Continue loop to get final response with tool results
                continue

            # No tool calls - this is the final response
            final_response = ai_response
            final_response["tool_results"] = all_tool_results
            break

        # Save assistant response to database
        if final_response:
            self.db.add_message(chat_id, "assistant", final_response.get("message", ""))

        total_time = time.time() - start_time
        debug_print("DONE", f"Request completed in {total_time:.2f}s ({iteration} iterations)", {
            "status": final_response.get("status", "ok") if final_response else "error",
            "message_preview": final_response.get("message", "")[:100] if final_response else "No response",
            "tool_calls": len(all_tool_results),
            "thinking": final_response.get("thinking", "")[:100] if final_response and final_response.get("thinking") else None
        })

        return final_response or {"status": "error", "message": "Max iterations reached without final response"}

    async def _get_current_context(self) -> dict:
        """Get context from current page state. Auto-navigates to orders if on unknown page."""
        if not self.extractor:
            return {"page_type": "unknown", "url": "Browser not initialized", "formatted": "Browser not initialized"}

        try:
            # Ensure we have a valid page (reopen if closed)
            page = await self.browser.ensure_page()
            # Update extractor's page reference
            self.extractor.page = page

            data = await self.extractor.extract_current_page()

            # If on unknown page (like welcome), navigate to orders to get useful context
            if data.get("page_type") == "unknown":
                debug_print("CONTEXT", "On unknown page, navigating to orders...")
                await self.browser.navigate("https://laboratoriofranz.orion-labs.com/ordenes")
                await self.browser.page.wait_for_timeout(2000)  # Wait for Vue.js
                data = await self.extractor.extract_current_page()
                debug_print("CONTEXT", f"Now on: {data.get('page_type')}")

            # Format data using optimized formatters (reduces tokens by ~50%)
            formatted = self._format_context(data)
            data["formatted"] = formatted

            return data
        except Exception as e:
            return {
                "page_type": "error",
                "url": self.browser.page.url if self.browser.page else "N/A",
                "error": str(e),
                "formatted": f"Error: {str(e)}"
            }

    def _format_context(self, data: dict) -> str:
        """Format extracted data using optimized formatters."""
        page_type = data.get("page_type", "unknown")

        if page_type == "ordenes_list":
            return format_ordenes_context(data.get("ordenes", []))
        elif page_type == "reportes":
            return format_reportes_context(data)
        elif page_type == "orden_edit":
            return format_orden_edit_context(data)
        elif page_type == "orden_create":
            # Basic format for create page
            exams = data.get("examenes_seleccionados", [])
            if exams:
                lines = ["# Nueva Orden"]
                lines.append(f"Paciente cargado: {'Sí' if data.get('paciente_cargado') else 'No'}")
                lines.append(f"Exámenes: {len(exams)}")
                for e in exams:
                    lines.append(f"  - {e.get('nombre', 'N/A')} ({e.get('valor', 'N/A')})")
                return "\n".join(lines)
            return "# Nueva Orden\nNo hay exámenes seleccionados"
        else:
            return f"Página: {page_type}\nURL: {data.get('url', 'N/A')}"

    def _format_history(self, history: List[Dict]) -> str:
        """Format chat history for the prompt."""
        if not history:
            return "No hay mensajes previos."

        formatted = []
        for msg in history[-10:]:  # Last 10 messages
            role = "Usuario" if msg["role"] == "user" else "Asistente"
            content = msg["content"][:300]  # Truncate long messages
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)

    async def on_new_chat(self, chat_id: str) -> dict:
        """Called when a new chat is created - loads initial context."""
        # Ensure initialized
        if not self.extractor:
            await self.initialize()

        try:
            # Navigate to ordenes and get list
            await self.browser.navigate("https://laboratoriofranz.orion-labs.com/ordenes")
            ordenes = await self.extractor.extract_ordenes_list()

            return {
                "status": "ready",
                "message": WELCOME_MESSAGE,
                "context": ordenes
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error al cargar órdenes: {str(e)}"
            }

    async def execute_approved(self, chat_id: str, edited_data: dict = None) -> dict:
        """
        Execute approved changes (possibly with user edits).

        Args:
            chat_id: Chat session ID
            edited_data: Data edited by user before approval

        Returns:
            Execution result
        """
        # Get the last plan from the chat
        plan = self.db.get_plan(chat_id)
        if not plan:
            return {
                "status": "error",
                "message": "No hay plan pendiente para ejecutar"
            }

        # If user edited data, update the plan
        if edited_data:
            plan["extracted_data"] = edited_data

        # Execute the plan
        results = []
        for step in plan.get("steps", []):
            if self.browser.is_action_forbidden(step):
                results.append({
                    "action": step.get("action"),
                    "success": False,
                    "error": "Acción prohibida: guardado/eliminación"
                })
                continue

            result = await self.browser.execute_action(step)
            results.append(result)

            if not result.get("success"):
                break

        all_success = all(r.get("success", False) for r in results)

        return {
            "status": "completed" if all_success else "error",
            "message": "Campos llenados. Por favor haz click en 'Guardar' en el navegador." if all_success else "Algunas acciones fallaron.",
            "results": results
        }

    async def continue_after_user_action(self, chat_id: str, action_type: str) -> dict:
        """
        Called after user completes a requested action (e.g., clicked Save).

        Args:
            chat_id: Chat session ID
            action_type: Type of action completed (save, validate, etc.)

        Returns:
            Next steps or completion message
        """
        if action_type == "save":
            return {
                "status": "completed",
                "message": "¡Guardado! ¿Necesitas ingresar más resultados?"
            }
        elif action_type == "validate":
            return {
                "status": "completed",
                "message": "¡Validado! ¿Algo más en lo que pueda ayudar?"
            }
        else:
            return {
                "status": "ready",
                "message": "Entendido. ¿En qué más puedo ayudarte?"
            }

    async def get_orders_summary(self) -> Dict[str, Any]:
        """Get a summary of recent orders."""
        if not self.extractor:
            await self.initialize()

        try:
            await self.browser.navigate("https://laboratoriofranz.orion-labs.com/ordenes")
            return await self.extractor.extract_ordenes_list()
        except Exception as e:
            return {
                "page_type": "error",
                "error": str(e)
            }
