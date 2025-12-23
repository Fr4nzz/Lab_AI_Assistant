# Lab Assistant AI Agent - Coding Plan

## Project Overview

Build an AI-powered laboratory assistant that helps lab staff enter exam results into the laboratoriofranz.orion-labs.com system. The AI agent receives text, images (handwritten notes), or audio instructions, interprets them, and controls the browser to fill in form fields.

**Critical Safety Rule**: The AI agent NEVER clicks "Guardar" (Save) or "Eliminar" (Delete) buttons. Only the human user can perform these actions.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React)                               │
│  ┌──────────────┐  ┌─────────────────────────────────────────────────┐  │
│  │   Sidebar    │  │              Chat Interface                      │  │
│  │  - Chats     │  │  [Messages with AI responses]                   │  │
│  │  - + New     │  │  [Data Review Table - editable]                 │  │
│  │              │  │  [Action Buttons: Approve/Cancel]               │  │
│  └──────────────┘  │  [Input: text/image/audio]                      │  │
│                    └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          BACKEND (FastAPI)                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      LabAgent (Orchestrator)                     │    │
│  │  - Receives user message + attachments                          │    │
│  │  - Builds context (orders list, current page state)             │    │
│  │  - Calls Gemini with structured prompt                          │    │
│  │  - Parses JSON response                                         │    │
│  │  - Executes tool calls                                          │    │
│  │  - Returns response to frontend                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│           │                    │                      │                  │
│           ▼                    ▼                      ▼                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────┐    │
│  │ GeminiHandler   │  │ BrowserManager  │  │ PageDataExtractor    │    │
│  │ (API key rot.)  │  │ (Playwright)    │  │ (scrapes page info)  │    │
│  └─────────────────┘  └─────────────────┘  └──────────────────────┘    │
│                                │                                         │
│                                ▼                                         │
│                    ┌──────────────────────┐                             │
│                    │ laboratoriofranz     │                             │
│                    │  .orion-labs.com     │                             │
│                    └──────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Page Data Extractors (Priority: HIGH)

Create specialized functions to extract structured data from each page type.

### 1.1 File: `backend/extractors.py`

```python
# Module containing all page data extraction logic
# Each function returns a structured dict ready for AI context

class PageDataExtractor:
    def __init__(self, page: Page):
        self.page = page
    
    async def detect_page_type(self) -> str:
        """Detect current page type from URL"""
        # Returns: "ordenes_list", "orden_create", "orden_edit", "reportes", "login", "unknown"
    
    async def extract_ordenes_list(self, limit: int = 20) -> dict:
        """Extract orders list from /ordenes page"""
        # Returns: {"ordenes": [...], "pagination": {...}, "filters_applied": {...}}
    
    async def extract_orden_edit(self) -> dict:
        """Extract order details from /ordenes/{id}/edit page"""
        # Returns: {"orden": {...}, "paciente": {...}, "examenes": [...], "totales": {...}}
    
    async def extract_reportes(self) -> dict:
        """Extract exam results from /reportes2 page"""
        # Returns: {"numero_orden": "...", "examenes": [...], "campos_editables": [...]}
    
    async def extract_orden_create(self) -> dict:
        """Extract create order form state"""
        # Returns: {"paciente_loaded": bool, "examenes_selected": [...], "totales": {...}}
```

### 1.2 Implementation Details

#### `extract_ordenes_list()` - Returns:
```json
{
  "page_type": "ordenes_list",
  "ordenes": [
    {
      "numero": "2512233",
      "fecha": "2025-12-23 10:14:17",
      "paciente": {
        "cedula": "1501238453",
        "nombre": "TAPUY ANDI ALEXANDRA JANETH",
        "edad": "29a",
        "sexo": "F"
      },
      "estado": "Validado",
      "valor": "$3.00",
      "id_interno": 14561
    }
  ],
  "total_ordenes": 20,
  "pagina_actual": 1
}
```

#### `extract_reportes()` - Returns:
```json
{
  "page_type": "reportes",
  "numero_orden": "2501181",
  "paciente": "CHANDI VILLARROEL FRANZ ALEXANDER",
  "examenes": [
    {
      "nombre": "BIOMETRÍA HEMÁTICA",
      "tipo_muestra": "Sangre Total EDTA",
      "estado": "Validado",
      "campos": [
        {
          "nombre": "Hemoglobina",
          "tipo": "input",
          "valor_actual": "16.4",
          "referencia": "[14.5 - 18.5]g/dL"
        },
        {
          "nombre": "Color",
          "tipo": "select",
          "valor_actual": "Amarillo",
          "opciones": ["Amarillo", "Amarillo Claro", "Ámbar", ...]
        }
      ]
    }
  ],
  "puede_guardar": true,
  "puede_validar": false
}
```

---

## Phase 2: AI Tool Definitions (Priority: HIGH)

Define the tools the AI agent can use. These are JSON-schema defined functions.

### 2.1 File: `backend/tools.py`

```python
TOOL_DEFINITIONS = [
    {
        "name": "navigate_to_ordenes",
        "description": "Navigate to the orders list page. Use this to see recent orders or search for a patient.",
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string",
                    "description": "Optional search query (patient name, cedula, or order number)"
                }
            },
            "required": []
        }
    },
    {
        "name": "navigate_to_reportes",
        "description": "Navigate to the results/reporting page for a specific order. Use this to view or edit exam results.",
        "parameters": {
            "type": "object",
            "properties": {
                "numero_orden": {
                    "type": "string",
                    "description": "The order number (e.g., '2512233')"
                }
            },
            "required": ["numero_orden"]
        }
    },
    {
        "name": "navigate_to_edit_orden",
        "description": "Navigate to edit an existing order. Use this to add or remove exams from an order.",
        "parameters": {
            "type": "object",
            "properties": {
                "id_interno": {
                    "type": "integer",
                    "description": "The internal ID of the order (from ordenes list)"
                }
            },
            "required": ["id_interno"]
        }
    },
    {
        "name": "navigate_to_create_orden",
        "description": "Navigate to create a new order. Use this when the patient doesn't have an existing order.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "fill_patient_cedula",
        "description": "Fill the patient identification field and press Enter to load patient data. Only works on create/edit order pages.",
        "parameters": {
            "type": "object",
            "properties": {
                "cedula": {
                    "type": "string",
                    "description": "Patient's cedula (ID number)"
                }
            },
            "required": ["cedula"]
        }
    },
    {
        "name": "add_exam_to_order",
        "description": "Add an exam to the current order. Only works on create/edit order pages.",
        "parameters": {
            "type": "object",
            "properties": {
                "exam_name": {
                    "type": "string",
                    "description": "Name or code of the exam to add (e.g., 'EMO', 'COPRO', 'BH')"
                }
            },
            "required": ["exam_name"]
        }
    },
    {
        "name": "fill_exam_result",
        "description": "Fill a specific field in the exam results. Only works on reportes page.",
        "parameters": {
            "type": "object",
            "properties": {
                "exam_name": {
                    "type": "string",
                    "description": "Name of the exam (e.g., 'BIOMETRÍA HEMÁTICA')"
                },
                "field_name": {
                    "type": "string",
                    "description": "Name of the field to fill (e.g., 'Hemoglobina')"
                },
                "value": {
                    "type": "string",
                    "description": "Value to enter"
                }
            },
            "required": ["exam_name", "field_name", "value"]
        }
    },
    {
        "name": "fill_multiple_results",
        "description": "Fill multiple exam result fields at once. More efficient than calling fill_exam_result multiple times.",
        "parameters": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "exam_name": {"type": "string"},
                            "field_name": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["exam_name", "field_name", "value"]
                    },
                    "description": "Array of results to fill"
                }
            },
            "required": ["results"]
        }
    },
    {
        "name": "open_new_tab",
        "description": "Open a new browser tab for a different patient/order. Useful for parallel work.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to open in new tab (e.g., reportes page for another order)"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "switch_to_tab",
        "description": "Switch to a specific browser tab.",
        "parameters": {
            "type": "object",
            "properties": {
                "tab_index": {
                    "type": "integer",
                    "description": "Index of the tab to switch to (0-based)"
                }
            },
            "required": ["tab_index"]
        }
    },
    {
        "name": "get_current_page_data",
        "description": "Get structured data from the current page. Use this to understand what's on screen.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "highlight_changes",
        "description": "Visually highlight fields that have been modified by the AI. Helps user review changes.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "request_user_action",
        "description": "Ask the user to perform an action (like clicking Save). The AI cannot click Save/Delete buttons.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["click_save", "click_validate", "confirm_data", "provide_info"],
                    "description": "What action to request from user"
                },
                "message": {
                    "type": "string",
                    "description": "Message to show the user explaining what they need to do"
                }
            },
            "required": ["action", "message"]
        }
    }
]
```

---

## Phase 3: AI Response Schema (Priority: HIGH)

Define the JSON schema for AI responses. The AI must ALWAYS respond in this format.

### 3.1 File: `backend/schemas.py`

```python
AI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "thinking": {
            "type": "string",
            "description": "AI's internal reasoning (shown in debug mode only)"
        },
        "message": {
            "type": "string",
            "description": "Message to display to the user in the chat"
        },
        "tool_calls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool": {
                        "type": "string",
                        "description": "Name of the tool to call"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Parameters for the tool"
                    }
                },
                "required": ["tool", "parameters"]
            },
            "description": "List of tools to execute in sequence"
        },
        "data_to_review": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "patient": {"type": "string"},
                            "exam": {"type": "string"},
                            "fields": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "string"},
                                        "previous_value": {"type": "string"},
                                        "editable": {"type": "boolean"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "description": "Data for user to review/edit before execution"
        },
        "status": {
            "type": "string",
            "enum": ["thinking", "executing", "waiting_for_user", "completed", "error"],
            "description": "Current status of the AI agent"
        },
        "next_step": {
            "type": "string",
            "description": "What will happen next (for user information)"
        }
    },
    "required": ["message", "status"]
}
```

### 3.2 Example AI Responses

#### Example 1: AI needs to navigate to see orders
```json
{
  "thinking": "User wants to add EMO results for patient Chandi. First I need to search for existing orders.",
  "message": "Voy a buscar las órdenes del paciente Chandi para ver si ya tiene una orden con EMO.",
  "tool_calls": [
    {
      "tool": "navigate_to_ordenes",
      "parameters": {"search_query": "Chandi"}
    }
  ],
  "status": "executing",
  "next_step": "Buscaré al paciente en las órdenes existentes"
}
```

#### Example 2: AI ready to fill results
```json
{
  "thinking": "Found the order. The reportes page has EMO exam. I can fill the values from the image.",
  "message": "Encontré la orden #2512233. Voy a ingresar los resultados del EMO que interpreté de la imagen.",
  "tool_calls": [
    {
      "tool": "fill_multiple_results",
      "parameters": {
        "results": [
          {"exam_name": "ELEMENTAL Y MICROSCOPICO DE ORINA", "field_name": "Color", "value": "Amarillo"},
          {"exam_name": "ELEMENTAL Y MICROSCOPICO DE ORINA", "field_name": "Aspecto", "value": "Transparente"},
          {"exam_name": "ELEMENTAL Y MICROSCOPICO DE ORINA", "field_name": "pH", "value": "6.0"}
        ]
      }
    },
    {
      "tool": "highlight_changes",
      "parameters": {}
    }
  ],
  "data_to_review": {
    "title": "Resultados a ingresar - EMO",
    "items": [
      {
        "patient": "CHANDI VILLARROEL FRANZ ALEXANDER",
        "exam": "ELEMENTAL Y MICROSCOPICO DE ORINA",
        "fields": [
          {"name": "Color", "value": "Amarillo", "previous_value": "", "editable": true},
          {"name": "Aspecto", "value": "Transparente", "previous_value": "", "editable": true},
          {"name": "pH", "value": "6.0", "previous_value": "", "editable": true}
        ]
      }
    ]
  },
  "status": "waiting_for_user",
  "next_step": "Revisa los datos. Si están correctos, haz click en 'Guardar' en el navegador."
}
```

#### Example 3: AI needs user to create order first
```json
{
  "thinking": "Patient doesn't have an order with EMO. Need to create one or add EMO to existing order.",
  "message": "El paciente tiene una orden pero no incluye el examen EMO. Necesito agregar el examen a la orden existente.",
  "tool_calls": [
    {
      "tool": "navigate_to_edit_orden",
      "parameters": {"id_interno": 14561}
    },
    {
      "tool": "add_exam_to_order",
      "parameters": {"exam_name": "EMO"}
    },
    {
      "tool": "request_user_action",
      "parameters": {
        "action": "click_save",
        "message": "He agregado el examen EMO a la orden. Por favor haz click en 'Guardar' para confirmar."
      }
    }
  ],
  "status": "waiting_for_user",
  "next_step": "Después de guardar, podré ingresar los resultados del EMO."
}
```

---

## Phase 4: System Prompt (Priority: HIGH)

### 4.1 File: `backend/prompts.py`

```python
SYSTEM_PROMPT = """Eres un asistente de laboratorio clínico especializado en el ingreso y edición de resultados de exámenes en el sistema Orion Labs (laboratoriofranz.orion-labs.com).

## TU ROL
- Ayudas al personal de laboratorio a ingresar resultados de exámenes
- Interpretas texto, imágenes de cuadernos manuscritos, y audio
- Controlas el navegador para llenar formularios
- NUNCA haces click en botones de "Guardar", "Validar" o "Eliminar" - solo el usuario puede hacerlo

## REGLAS CRÍTICAS
1. **NUNCA** ejecutes acciones de guardado o eliminación
2. **SIEMPRE** muestra los datos al usuario para revisión antes de ejecutar
3. **SIEMPRE** responde en formato JSON válido
4. Si no encuentras información suficiente, **PREGUNTA** al usuario
5. Si un examen no existe en la orden, **PRIMERO** agrega el examen a la orden

## FLUJO DE TRABAJO TÍPICO

### Para ingresar resultados de un paciente existente:
1. Buscar al paciente en la lista de órdenes
2. Ir a la página de reportes de esa orden
3. Verificar que el examen existe en la orden
4. Si no existe, ir a editar orden → agregar examen → pedir al usuario que guarde
5. Llenar los campos del examen
6. Resaltar cambios y pedir al usuario que guarde

### Para un paciente nuevo:
1. Ir a crear nueva orden
2. Ingresar cédula del paciente
3. Agregar los exámenes necesarios
4. Pedir al usuario que guarde
5. Ir a reportes e ingresar resultados

## INTERPRETACIÓN DE ABREVIATURAS (EMO)
- Color: AM/A = Amarillo, AP = Amarillo Claro, AI = Amarillo Intenso
- Aspecto: TP = Transparente, LT = Ligeramente Turbio, T = Turbio
- pH: valores numéricos (5.0, 6.0, 7.0, etc.)
- Leucocitos/Proteínas: NEG = Negativo, TRZ = Trazas, + = Positivo leve

## INTERPRETACIÓN DE ABREVIATURAS (Coproparasitario)
- Consistencia: D = Dura, B = Blanda, S = Semiblanda, L = Líquida
- Si no hay parásitos: "No se observan parásitos"

## HERRAMIENTAS DISPONIBLES
{tools_description}

## FORMATO DE RESPUESTA
SIEMPRE responde con un JSON válido con esta estructura:
```json
{
  "thinking": "Tu razonamiento interno",
  "message": "Mensaje para mostrar al usuario en español",
  "tool_calls": [{"tool": "nombre", "parameters": {...}}],
  "data_to_review": {...},  // Opcional: datos para que el usuario revise
  "status": "executing|waiting_for_user|completed|error",
  "next_step": "Qué pasará después"
}
```

## CONTEXTO ACTUAL
{current_context}

## HISTORIAL DE CONVERSACIÓN
{chat_history}
"""
```

---

## Phase 5: Tool Executor (Priority: HIGH)

### 5.1 File: `backend/tool_executor.py`

```python
class ToolExecutor:
    """Executes AI tool calls safely"""
    
    def __init__(self, browser_manager: BrowserManager, extractor: PageDataExtractor):
        self.browser = browser_manager
        self.extractor = extractor
        self.tabs = []  # Track open tabs
    
    async def execute(self, tool_name: str, parameters: dict) -> dict:
        """Execute a tool and return result"""
        
        method = getattr(self, f"_exec_{tool_name}", None)
        if not method:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        try:
            result = await method(parameters)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _exec_navigate_to_ordenes(self, params: dict) -> dict:
        """Navigate to orders list with optional search"""
        await self.browser.navigate("https://laboratoriofranz.orion-labs.com/ordenes")
        
        if params.get("search_query"):
            search_input = self.browser.page.locator('input[placeholder*="Buscar"]')
            await search_input.fill(params["search_query"])
            await self.browser.page.keyboard.press("Enter")
            await self.browser.page.wait_for_timeout(2000)
        
        return await self.extractor.extract_ordenes_list()
    
    async def _exec_navigate_to_reportes(self, params: dict) -> dict:
        """Navigate to reportes page for an order"""
        url = f"https://laboratoriofranz.orion-labs.com/reportes2?numeroOrden={params['numero_orden']}"
        await self.browser.navigate(url)
        await self.browser.page.wait_for_timeout(2000)
        return await self.extractor.extract_reportes()
    
    async def _exec_navigate_to_edit_orden(self, params: dict) -> dict:
        """Navigate to edit order page"""
        url = f"https://laboratoriofranz.orion-labs.com/ordenes/{params['id_interno']}/edit"
        await self.browser.navigate(url)
        await self.browser.page.wait_for_timeout(2000)
        return await self.extractor.extract_orden_edit()
    
    async def _exec_fill_exam_result(self, params: dict) -> dict:
        """Fill a single exam result field"""
        exam_name = params["exam_name"]
        field_name = params["field_name"]
        value = params["value"]
        
        # Implementation using the proven JavaScript from test_edit_reportes.py
        result = await self.browser.page.evaluate("""...""")
        return result
    
    async def _exec_fill_multiple_results(self, params: dict) -> dict:
        """Fill multiple results efficiently"""
        results = []
        for item in params["results"]:
            result = await self._exec_fill_exam_result(item)
            results.append(result)
        return {"filled": len(results), "results": results}
    
    async def _exec_highlight_changes(self, params: dict) -> dict:
        """Inject CSS to highlight modified fields"""
        # Uses the CSS injection from test_edit_reportes.py
        await self.browser.page.evaluate("""...""")
        return {"highlighted": True}
    
    async def _exec_open_new_tab(self, params: dict) -> dict:
        """Open new browser tab"""
        new_page = await self.browser.context.new_page()
        await new_page.goto(params["url"])
        self.tabs.append(new_page)
        return {"tab_index": len(self.tabs) - 1, "url": params["url"]}
    
    async def _exec_switch_to_tab(self, params: dict) -> dict:
        """Switch to specific tab"""
        index = params["tab_index"]
        if index < len(self.tabs):
            self.browser.page = self.tabs[index]
            await self.browser.page.bring_to_front()
            return {"switched_to": index}
        return {"error": f"Tab {index} not found"}
```

---

## Phase 6: Updated Lab Agent (Priority: HIGH)

### 6.1 File: `backend/lab_agent.py` (Refactored)

```python
class LabAgent:
    """Main AI agent that orchestrates everything"""
    
    def __init__(self, gemini: GeminiHandler, browser: BrowserManager, db: Database):
        self.gemini = gemini
        self.browser = browser
        self.db = db
        self.extractor = PageDataExtractor(browser.page)
        self.executor = ToolExecutor(browser, self.extractor)
    
    async def process_message(
        self,
        chat_id: str,
        message: str,
        attachments: List[dict] = None
    ) -> dict:
        """Process user message and return AI response"""
        
        # 1. Get chat history
        history = self.db.get_messages(chat_id, limit=20)
        
        # 2. Get current page context
        page_context = await self._get_current_context()
        
        # 3. Build prompt
        prompt = self._build_prompt(message, history, page_context)
        
        # 4. Build content list (text + images + audio)
        contents = self._build_contents(prompt, attachments)
        
        # 5. Call Gemini
        response_text, success = await self.gemini.send_request(
            system_prompt=SYSTEM_PROMPT.format(
                tools_description=self._format_tools_description(),
                current_context=json.dumps(page_context, ensure_ascii=False),
                chat_history=self._format_history(history)
            ),
            contents=contents
        )
        
        if not success:
            return {"status": "error", "message": f"Error: {response_text}"}
        
        # 6. Parse AI response
        try:
            ai_response = json.loads(response_text)
        except json.JSONDecodeError:
            return {"status": "error", "message": "Error parsing AI response"}
        
        # 7. Execute tool calls if any
        if ai_response.get("tool_calls"):
            tool_results = []
            for call in ai_response["tool_calls"]:
                result = await self.executor.execute(call["tool"], call["parameters"])
                tool_results.append(result)
            ai_response["tool_results"] = tool_results
        
        # 8. Save messages to database
        self.db.add_message(chat_id, "user", message)
        self.db.add_message(chat_id, "assistant", ai_response.get("message", ""))
        
        return ai_response
    
    async def _get_current_context(self) -> dict:
        """Get context from current page state"""
        page_type = await self.extractor.detect_page_type()
        
        if page_type == "ordenes_list":
            return await self.extractor.extract_ordenes_list()
        elif page_type == "reportes":
            return await self.extractor.extract_reportes()
        elif page_type == "orden_edit":
            return await self.extractor.extract_orden_edit()
        elif page_type == "orden_create":
            return await self.extractor.extract_orden_create()
        else:
            return {"page_type": "unknown", "url": self.browser.page.url}
    
    async def on_new_chat(self, chat_id: str) -> dict:
        """Called when a new chat is created - loads initial context"""
        # Navigate to ordenes and get list
        await self.browser.navigate("https://laboratoriofranz.orion-labs.com/ordenes")
        ordenes = await self.extractor.extract_ordenes_list()
        
        return {
            "status": "ready",
            "message": "¡Hola! Soy tu asistente de laboratorio. Veo las órdenes recientes. ¿Qué resultados necesitas ingresar?",
            "context": ordenes
        }
```

---

## Phase 7: Frontend Updates (Priority: MEDIUM)

### 7.1 Update `ChatInterface.tsx`

Add support for:
- Displaying `data_to_review` as editable table
- Handling `status` to show appropriate UI
- Showing `next_step` to guide user
- Approve/Cancel buttons when `status === "waiting_for_user"`

### 7.2 New Component: `AIStatusIndicator.tsx`

```tsx
// Shows current AI status: thinking, executing, waiting, etc.
// With animations and clear user guidance
```

### 7.3 New Component: `DataReviewTable.tsx`

```tsx
// Displays data_to_review from AI response
// Allows user to edit values before AI executes
// Approve/Reject buttons
```

---

## Phase 8: API Endpoints Update (Priority: MEDIUM)

### 8.1 Update `backend/main.py`

```python
@app.post("/api/chat/new")
async def create_chat_with_context():
    """Create new chat and return initial context (orders list)"""
    chat = db.create_chat()
    initial_context = await agent.on_new_chat(chat["id"])
    return {"chat": chat, "initial_context": initial_context}

@app.post("/api/chat/{chat_id}/approve")
async def approve_ai_action(chat_id: str, data: ApproveRequest):
    """User approved the AI's proposed changes"""
    # Execute the pending tool calls with possibly edited data
    result = await agent.execute_approved(chat_id, data.edited_data)
    return result

@app.post("/api/chat/{chat_id}/user-action-complete")
async def user_action_complete(chat_id: str, action: UserActionComplete):
    """User completed a requested action (e.g., clicked Save)"""
    # AI can continue with next steps
    result = await agent.continue_after_user_action(chat_id, action.action_type)
    return result

@app.get("/api/browser/tabs")
async def get_browser_tabs():
    """Get list of open browser tabs"""
    return {"tabs": agent.executor.tabs}
```

---

## Phase 9: Testing & Iteration (Priority: MEDIUM)

### 9.1 Test Scenarios

1. **Simple case**: User sends image of EMO results for existing patient with existing order
2. **Add exam case**: Patient exists but doesn't have the exam → add exam → wait for save → fill results
3. **New patient case**: Patient doesn't exist → create order → wait for save → fill results
4. **Multiple patients**: User sends image with results for 3 different patients → parallel tabs

### 9.2 Test Files

```
backend/
  tests/
    test_extractors.py
    test_tool_executor.py
    test_lab_agent.py
    test_integration.py
```

---

## Implementation Order

### Week 1: Core Infrastructure
1. ✅ Browser control basics (already done)
2. [ ] `extractors.py` - All page data extractors
3. [ ] `tools.py` - Tool definitions
4. [ ] `schemas.py` - Response schemas

### Week 2: AI Integration
5. [ ] `prompts.py` - System prompt
6. [ ] `tool_executor.py` - Tool execution
7. [ ] `lab_agent.py` - Refactored agent

### Week 3: Frontend & Polish
8. [ ] Frontend components update
9. [ ] API endpoints update
10. [ ] Testing & bug fixes

---

## File Structure (Final)

```
lab-assistant/
├── main.py                      # Root launcher
├── backend/
│   ├── main.py                  # FastAPI app
│   ├── config.py                # Configuration
│   ├── gemini_handler.py        # Gemini API with key rotation
│   ├── browser_manager.py       # Playwright browser control
│   ├── database.py              # SQLite persistence
│   ├── extractors.py            # Page data extractors (NEW)
│   ├── tools.py                 # Tool definitions (NEW)
│   ├── schemas.py               # JSON schemas (NEW)
│   ├── prompts.py               # System prompts (NEW)
│   ├── tool_executor.py         # Tool execution (NEW)
│   ├── lab_agent.py             # Main agent (REFACTORED)
│   └── site_knowledge/
│       ├── emo.json
│       └── coproparasitario.json
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── ChatInterface.tsx
│       │   ├── DataReviewTable.tsx (NEW)
│       │   ├── AIStatusIndicator.tsx (NEW)
│       │   └── ...
│       └── api/
│           └── client.ts
└── tests/
    └── ...
```

---

## Notes for Claude Code

1. **Start with extractors.py** - This is the foundation. Use the working JavaScript from `inspect_ordenes.py`, `inspect_reportes.py`, and `inspect_edit_orden.py`.

2. **Test each tool individually** before integrating with the AI agent.

3. **The AI must ALWAYS respond in JSON** - Use `response_mime_type="application/json"` in Gemini calls.

4. **Use the proven patterns** from the test scripts for browser interactions.

5. **Keep the highlight CSS injection** - It's important for user review.

6. **Remember forbidden actions** - The `FORBIDDEN_WORDS` list in `browser_manager.py` is critical.
