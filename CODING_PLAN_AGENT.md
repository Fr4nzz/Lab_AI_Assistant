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

**Design Principles:**
1. **Short names** to minimize token output costs
2. **Context-first** - AI receives orders list with first message
3. **No search needed** - If patient not in list → CREATE NEW ORDER (old orders have old data)
4. **Reuse tabs** - When retrieving data, keep tab open for editing
5. **Auto-highlight** - Fields are highlighted automatically when edited

### 2.1 Logic: Patient Not in Orders List

```
┌─────────────────────────────────────────────────────────────────┐
│ Patient NOT in orders list?                                      │
│                                                                  │
│ DON'T search for old orders!                                    │
│ → Old orders have old/validated data                            │
│ → New exam results need a NEW order                             │
│                                                                  │
│ INSTEAD: Create new order directly                              │
│ → create_orden(cedula="...", exams=["EMO", ...])               │
│ → Ask user to click Save                                        │
│ → Then fill results                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Typical Flow (Patient in List)

```
┌─────────────────────────────────────────────────────────────────┐
│ FIRST MESSAGE: AI receives context with recent orders list      │
│                                                                 │
│ User: "Ingresa EMO para Chandi" + image                        │
│                                                                 │
│ AI already has:                                                 │
│ {                                                               │
│   "ordenes": [                                                  │
│     {"num": "2512233", "paciente": "CHANDI...", "id": 14561},  │
│     ...                                                         │
│   ]                                                             │
│ }                                                               │
│                                                                 │
│ AI finds Chandi in list → Use existing order!                  │
│ AI calls: get_reportes(orden="2512233")  ← Gets data + keeps tab│
│ AI calls: fill_many(...)                  ← Edits in same tab  │
│ AI calls: ask_user(action="save")         ← User clicks Guardar│
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 File: `backend/tools.py`

```python
TOOL_DEFINITIONS = [
    # ============================================================
    # DATA RETRIEVAL TOOLS (Background - keeps tab open for reuse)
    # ============================================================
    {
        "name": "get_reportes",
        "description": "Get exam results for an order. KEEPS TAB OPEN for subsequent edits.",
        "parameters": {
            "type": "object",
            "properties": {
                "orden": {"type": "string", "description": "Order number"}
            },
            "required": ["orden"]
        },
        "execution_mode": "background_keep_tab"
    },
    {
        "name": "get_orden",
        "description": "Get order details (exams list, patient info). Use to check if exam exists before editing.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Internal order ID"}
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
        "description": "Create new order. Use when patient is NOT in the orders list.",
        "parameters": {
            "type": "object",
            "properties": {
                "cedula": {"type": "string", "description": "Patient cedula"},
                "exams": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of exam codes to add (e.g., ['EMO', 'BH'])"
                }
            },
            "required": ["cedula", "exams"]
        },
        "execution_mode": "visible"
    },
    {
        "name": "add_exam",
        "description": "Add exam to existing order (navigates to edit page).",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Internal order ID"},
                "exam": {"type": "string", "description": "Exam code"}
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
        "description": "Fill a single exam result field. Auto-highlights the modified field.",
        "parameters": {
            "type": "object",
            "properties": {
                "e": {"type": "string", "description": "Exam name"},
                "f": {"type": "string", "description": "Field name"},
                "v": {"type": "string", "description": "Value"}
            },
            "required": ["e", "f", "v"]
        },
        "execution_mode": "visible",
        "auto_highlight": true
    },
    {
        "name": "fill_many",
        "description": "Fill multiple exam result fields. Auto-highlights all modified fields.",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "e": {"type": "string"},
                            "f": {"type": "string"},
                            "v": {"type": "string"}
                        },
                        "required": ["e", "f", "v"]
                    }
                }
            },
            "required": ["data"]
        },
        "execution_mode": "visible",
        "auto_highlight": true
    },
    
    # ============================================================
    # UI TOOLS
    # ============================================================
    {
        "name": "hl",
        "description": "Highlight specific fields for user attention (without editing them).",
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Field names to highlight"
                },
                "color": {
                    "type": "string",
                    "enum": ["yellow", "green", "red", "blue"],
                    "description": "Highlight color (default: yellow)"
                }
            },
            "required": ["fields"]
        },
        "execution_mode": "visible"
    },
    {
        "name": "ask_user",
        "description": "Request user action (save, validate, provide info).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["save", "validate", "info"]
                },
                "msg": {"type": "string", "description": "Message for user"}
            },
            "required": ["action", "msg"]
        },
        "execution_mode": "visible"
    }
]
```

### 2.4 Execution Modes Explained

```python
EXECUTION_MODES = {
    "background": {
        # Opens hidden tab, executes, closes tab, returns data
        "headless": True,
        "keep_tab": False
    },
    "background_keep_tab": {
        # Opens tab (hidden initially), executes, KEEPS tab for reuse
        # Tab becomes visible when fill/fill_many is called
        "headless": True,
        "keep_tab": True,
        "show_on_edit": True
    },
    "visible": {
        # Uses visible browser, user sees everything
        "headless": False,
        "keep_tab": True
    }
}
```

### 2.5 Auto-Highlight Behavior

When `auto_highlight: true` is set on a tool:
1. After filling a field, automatically add CSS highlight
2. Show value change indicator: `16.4 → 15.5`
3. Scroll to first modified field
4. No need for AI to call separate highlight tool

```python
# In tool_executor.py, fill operations automatically do:
async def _exec_fill(self, p: dict) -> dict:
    result = await self._fill_field(p)
    
    if result.get("ok"):
        # Auto-highlight is built into the fill operation
        await self._highlight_field(p["f"], result["prev"], result["new"])
    
    return result
```

---

## Phase 3: AI Response Schema (Priority: HIGH)

Define the JSON schema for AI responses. The AI must ALWAYS respond in this format.

**Note:** Gemini 2.5+ has built-in thinking that's separate from the response. We don't need a `thinking` field in our schema - Gemini handles it internally.

### 3.1 File: `backend/schemas.py`

```python
AI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "Message to display to the user in the chat (Spanish)"
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
            "description": "List of tools to execute in sequence"
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
                            "f": {"type": "string", "description": "Field name"},
                            "v": {"type": "string", "description": "New value"},
                            "prev": {"type": "string", "description": "Previous value"}
                        }
                    }
                }
            },
            "description": "Data for user to review before saving"
        },
        "status": {
            "type": "string",
            "enum": ["executing", "waiting_for_user", "completed", "error"]
        },
        "next_step": {
            "type": "string",
            "description": "What will happen next (optional)"
        }
    },
    "required": ["message", "status"]
}
```

### 3.2 Example AI Responses

#### Example 1: Typical flow - patient in context
```json
{
  "message": "Encontré a Chandi en las órdenes. Obteniendo resultados...",
  "tool_calls": [
    {"tool": "get_reportes", "parameters": {"orden": "2501181"}}
  ],
  "status": "executing"
}
```

After get_reportes returns (tab ready for editing):
```json
{
  "message": "Ingresando resultados del EMO...",
  "tool_calls": [
    {"tool": "fill_many", "parameters": {
      "data": [
        {"e": "ELEMENTAL Y MICROSCOPICO DE ORINA", "f": "Color", "v": "Amarillo"},
        {"e": "ELEMENTAL Y MICROSCOPICO DE ORINA", "f": "Aspecto", "v": "Transparente"},
        {"e": "ELEMENTAL Y MICROSCOPICO DE ORINA", "f": "pH", "v": "6.0"}
      ]
    }},
    {"tool": "ask_user", "parameters": {"action": "save", "msg": "Revisa los datos resaltados y haz click en Guardar"}}
  ],
  "data_to_review": {
    "patient": "CHANDI VILLARROEL FRANZ ALEXANDER",
    "exam": "EMO",
    "changes": [
      {"f": "Color", "v": "Amarillo"},
      {"f": "Aspecto", "v": "Transparente"},
      {"f": "pH", "v": "6.0"}
    ]
  },
  "status": "waiting_for_user"
}
```

#### Example 2: Patient NOT in list - create new order (don't search!)
```json
{
  "message": "Martinez no está en las órdenes recientes. Creando nueva orden...",
  "tool_calls": [
    {"tool": "create_orden", "parameters": {
      "cedula": "1234567890",
      "exams": ["EMO", "BH"]
    }},
    {"tool": "ask_user", "parameters": {"action": "save", "msg": "Creé la orden. Haz click en Guardar."}}
  ],
  "status": "waiting_for_user",
  "next_step": "Después de guardar, ingresaré los resultados"
}
```

#### Example 3: Need to add exam to existing order
```json
{
  "message": "La orden no tiene EMO. Agregándolo...",
  "tool_calls": [
    {"tool": "add_exam", "parameters": {"id": 4282, "exam": "EMO"}},
    {"tool": "ask_user", "parameters": {"action": "save", "msg": "Agregué EMO. Haz click en Guardar."}}
  ],
  "status": "waiting_for_user"
}
```

#### Example 4: Highlight fields for user attention
```json
{
  "message": "Estos valores están fuera del rango de referencia:",
  "tool_calls": [
    {"tool": "hl", "parameters": {"fields": ["Hemoglobina", "Hematocrito"], "color": "red"}}
  ],
  "status": "completed"
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

### Para ingresar resultados de un paciente EN LA LISTA de órdenes:
1. Encontrar al paciente en la lista de órdenes (ya la tienes en el contexto)
2. Usar get_reportes para obtener los campos del examen
3. Verificar que el examen existe en la orden
4. Si no existe, usar add_exam → pedir al usuario que guarde
5. Llenar los campos con fill_many (se resaltan automáticamente)
6. Pedir al usuario que guarde

### Para un paciente que NO ESTÁ en la lista de órdenes:
1. NO busques órdenes antiguas (tienen datos viejos)
2. Crear nueva orden con create_orden (cédula + exámenes)
3. Pedir al usuario que guarde
4. Luego usar get_reportes e ingresar resultados

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
    """Executes AI tool calls with tab reuse and auto-highlight"""
    
    def __init__(self, browser_manager: BrowserManager):
        self.browser = browser_manager
        self.active_tabs = {}  # {orden_num: Page} - reusable tabs
        self.bg_context = None  # Background browser context
    
    async def init_background_context(self):
        """Initialize hidden browser for background operations"""
        if not self.bg_context:
            self.bg_context = await self.browser.playwright.chromium.launch_persistent_context(
                user_data_dir=self.browser.user_data_dir,
                headless=True,
                channel="msedge"
            )
    
    async def execute(self, tool_name: str, params: dict) -> dict:
        """Execute a tool and return result"""
        method = getattr(self, f"_exec_{tool_name}", None)
        if not method:
            return {"ok": False, "err": f"Unknown: {tool_name}"}
        
        try:
            return {"ok": True, **await method(params)}
        except Exception as e:
            return {"ok": False, "err": str(e)}
    
    # ============================================================
    # BACKGROUND TOOLS
    # ============================================================
    
    async def _exec_get_reportes(self, p: dict) -> dict:
        """Get reportes data AND keep tab open for editing"""
        orden = p["orden"]
        
        # Check if tab already exists for this order
        if orden in self.active_tabs:
            page = self.active_tabs[orden]
            await page.reload()
        else:
            # Create new tab (hidden initially, will show on edit)
            page = await self.browser.context.new_page()
            self.active_tabs[orden] = page
        
        url = f"https://laboratoriofranz.orion-labs.com/reportes2?numeroOrden={orden}"
        await page.goto(url, timeout=30000)
        await page.wait_for_timeout(2000)
        
        # Inject highlight styles preemptively
        await self._inject_highlight_styles(page)
        
        data = await page.evaluate(EXTRACT_REPORTES_JS)
        return {"orden": orden, "tab_ready": True, **data}
    
    async def _exec_get_orden(self, p: dict) -> dict:
        """Get order details - background"""
        await self.init_background_context()
        page = await self._get_bg_page()
        
        url = f"https://laboratoriofranz.orion-labs.com/ordenes/{p['id']}/edit"
        await page.goto(url, timeout=30000)
        await page.wait_for_timeout(1500)
        
        return await page.evaluate(EXTRACT_ORDEN_EDIT_JS)
    
    # ============================================================
    # ORDER MANAGEMENT TOOLS (Visible)
    # ============================================================
    
    async def _exec_create_orden(self, p: dict) -> dict:
        """Create new order with patient and exams"""
        page = self.browser.page
        await page.goto("https://laboratoriofranz.orion-labs.com/ordenes/create")
        await page.wait_for_timeout(1000)
        
        # Fill cedula
        cedula_input = page.locator('#identificacion')
        await cedula_input.fill(p["cedula"])
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)
        
        # Add each exam
        for exam in p.get("exams", []):
            search = page.locator('#buscar-examen-input')
            await search.fill(exam)
            await page.wait_for_timeout(800)
            add_btn = page.locator(f'button[id*="examen"]').first
            await add_btn.click()
            await page.wait_for_timeout(500)
        
        return {"created": True, "cedula": p["cedula"], "exams": p.get("exams", [])}
    
    async def _exec_add_exam(self, p: dict) -> dict:
        """Add exam to existing order"""
        page = self.browser.page
        url = f"https://laboratoriofranz.orion-labs.com/ordenes/{p['id']}/edit"
        await page.goto(url)
        await page.wait_for_timeout(1500)
        
        search = page.locator('#buscar-examen-input')
        await search.fill(p["exam"])
        await page.wait_for_timeout(800)
        
        add_btn = page.locator('button[id*="examen"]').first
        await add_btn.click()
        
        return {"added": p["exam"], "order_id": p["id"]}
    
    # ============================================================
    # RESULT EDITING TOOLS (Visible, Auto-Highlight)
    # ============================================================
    
    async def _exec_fill(self, p: dict) -> dict:
        """Fill single field with auto-highlight"""
        # Get the tab for this order (created by get_reportes)
        page = self._get_active_page()
        
        # Make tab visible
        await page.bring_to_front()
        
        result = await page.evaluate("""
            (params) => {
                const rows = document.querySelectorAll('tr.parametro');
                for (const row of rows) {
                    const label = row.querySelector('td:first-child')?.innerText?.trim();
                    if (!label || !label.includes(params.f)) continue;
                    
                    const input = row.querySelector('input');
                    const select = row.querySelector('select');
                    const control = input || select;
                    
                    if (!control) continue;
                    
                    const prev = input ? input.value : select.options[select.selectedIndex]?.text;
                    
                    if (input) {
                        input.value = params.v;
                        input.dispatchEvent(new Event('input', {bubbles: true}));
                        input.dispatchEvent(new Event('change', {bubbles: true}));
                    } else {
                        // Find matching option for select
                        for (const opt of select.options) {
                            if (opt.text.toLowerCase().includes(params.v.toLowerCase())) {
                                select.value = opt.value;
                                select.dispatchEvent(new Event('change', {bubbles: true}));
                                break;
                            }
                        }
                    }
                    
                    // AUTO-HIGHLIGHT
                    control.classList.add('ai-modified');
                    row.classList.add('ai-modified-row');
                    
                    // Add change indicator
                    const indicator = document.createElement('span');
                    indicator.className = 'ai-change-badge';
                    indicator.textContent = prev + ' → ' + params.v;
                    control.parentNode.appendChild(indicator);
                    
                    // Scroll into view
                    control.scrollIntoView({behavior: 'smooth', block: 'center'});
                    
                    return {field: label, prev: prev, new: params.v};
                }
                return {err: 'Field not found: ' + params.f};
            }
        """, {"e": p["e"], "f": p["f"], "v": p["v"]})
        
        return result
    
    async def _exec_fill_many(self, p: dict) -> dict:
        """Fill multiple fields with auto-highlight"""
        results = []
        for item in p["data"]:
            r = await self._exec_fill(item)
            results.append(r)
        
        filled = len([r for r in results if "field" in r])
        return {"filled": filled, "total": len(p["data"]), "details": results}
    
    # ============================================================
    # UI TOOLS
    # ============================================================
    
    async def _exec_hl(self, p: dict) -> dict:
        """Highlight specific fields (without editing)"""
        page = self._get_active_page()
        color_map = {
            "yellow": "#fef3c7",
            "green": "#d1fae5", 
            "red": "#fee2e2",
            "blue": "#dbeafe"
        }
        color = color_map.get(p.get("color", "yellow"), "#fef3c7")
        
        await page.evaluate("""
            (params) => {
                const rows = document.querySelectorAll('tr.parametro');
                for (const row of rows) {
                    const label = row.querySelector('td:first-child')?.innerText?.trim();
                    for (const field of params.fields) {
                        if (label && label.includes(field)) {
                            row.style.backgroundColor = params.color;
                            row.scrollIntoView({behavior: 'smooth', block: 'center'});
                        }
                    }
                }
            }
        """, {"fields": p["fields"], "color": color})
        
        return {"highlighted": p["fields"]}
    
    async def _exec_ask_user(self, p: dict) -> dict:
        """Request user action"""
        return {
            "waiting": True,
            "action": p["action"],
            "msg": p["msg"]
        }
    
    # ============================================================
    # HELPERS
    # ============================================================
    
    async def _get_bg_page(self):
        """Get or create background page"""
        if self.bg_context.pages:
            return self.bg_context.pages[0]
        return await self.bg_context.new_page()
    
    def _get_active_page(self):
        """Get the most recent active tab, or main browser page"""
        if self.active_tabs:
            return list(self.active_tabs.values())[-1]
        return self.browser.page
    
    async def _inject_highlight_styles(self, page):
        """Inject CSS for highlighting"""
        await page.evaluate("""
            () => {
                if (document.getElementById('ai-styles')) return;
                const style = document.createElement('style');
                style.id = 'ai-styles';
                style.textContent = `
                    .ai-modified {
                        background-color: #fef3c7 !important;
                        border: 2px solid #f59e0b !important;
                        box-shadow: 0 0 8px rgba(245, 158, 11, 0.4) !important;
                    }
                    .ai-modified-row {
                        background-color: #fffbeb !important;
                    }
                    .ai-change-badge {
                        display: inline-block;
                        background: #dc2626;
                        color: white;
                        padding: 2px 6px;
                        border-radius: 4px;
                        font-size: 11px;
                        margin-left: 8px;
                        animation: pulse 1.5s infinite;
                    }
                    @keyframes pulse {
                        0%, 100% { opacity: 1; }
                        50% { opacity: 0.7; }
                    }
                `;
                document.head.appendChild(style);
            }
        """)
```

### 5.2 JavaScript Constants for Data Extraction

```python
EXTRACT_ORDENES_JS = r"""
() => {
    return Array.from(document.querySelectorAll('table tbody tr')).slice(0, 20).map(row => {
        const cells = row.querySelectorAll('td');
        let id = null;
        const dr = row.querySelector('[data-registro]');
        if (dr) try { id = JSON.parse(dr.getAttribute('data-registro')).id; } catch(e) {}
        const txt = cells[2]?.innerText?.split('\n') || [];
        return {
            num: cells[0]?.innerText?.trim(),
            fecha: cells[1]?.innerText?.trim().replace(/\n/g, ' '),
            cedula: txt[0]?.split(' ')[0],
            paciente: txt[1] || '',
            estado: cells[3]?.innerText?.trim(),
            id: id
        };
    });
}
"""

EXTRACT_REPORTES_JS = r"""
() => {
    const examenes = [];
    let current = null;
    
    document.querySelectorAll('tr.examen, tr.parametro').forEach(row => {
        if (row.classList.contains('examen')) {
            if (current && current.campos.length) examenes.push(current);
            current = {nombre: row.innerText.trim().split('\n')[0], campos: []};
        } else if (current) {
            const cells = row.querySelectorAll('td');
            const sel = cells[1]?.querySelector('select');
            const inp = cells[1]?.querySelector('input');
            if (sel || inp) {
                current.campos.push({
                    f: cells[0]?.innerText?.trim(),
                    tipo: sel ? 'select' : 'input',
                    val: sel ? sel.options[sel.selectedIndex]?.text : inp?.value,
                    ref: cells[2]?.innerText?.trim() || null
                });
            }
        }
    });
    if (current && current.campos.length) examenes.push(current);
    return {examenes};
}
"""

EXTRACT_ORDEN_EDIT_JS = r"""
() => {
    const examenes = [];
    document.querySelectorAll('#examenes-seleccionados tbody tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        const nombre = cells[0]?.innerText?.trim();
        const valor = cells[1]?.innerText?.trim();
        const canDelete = !row.querySelector('button[disabled]');
        if (nombre) examenes.push({nombre, valor, canDelete});
    });
    return {examenes};
}
"""
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

7. **Background vs Visible execution** - Use headless=True for data retrieval, headless=False for user-facing operations.

---

## Quick Reference: Tools (Final - 7 tools)

| Tool | Mode | Auto-HL | Description |
|------|------|---------|-------------|
| `get_reportes` | BG+Tab | - | Get exam results, **keeps tab open** |
| `get_orden` | BG | - | Get order details (exams list) |
| `create_orden` | VIS | - | Create new order with cedula + exams |
| `add_exam` | VIS | - | Add exam to existing order |
| `fill` | VIS | ✅ | Fill single field (auto-highlights) |
| `fill_many` | VIS | ✅ | Fill multiple fields (auto-highlights) |
| `hl` | VIS | - | Highlight fields (without editing) |
| `ask_user` | VIS | - | Request user action (save/validate) |

**Modes:**
- **BG** = Background (headless, user doesn't see)
- **BG+Tab** = Background but keeps tab for reuse
- **VIS** = Visible (user sees browser)

**Note:** No `search` tool! If patient not in orders list → create new order.

---

## Model Configuration

```dotenv
# .env
GEMINI_MODEL=gemini-2.5-flash-preview-05-20
```

Gemini 2.5+ has built-in thinking that's separate from the response output. The API handles this internally via `thinking_config`. See `gemini_handler.py` for implementation.

---

## Key Optimizations Summary

### 1. Context-First Approach
- Orders list sent with first message
- AI doesn't need to search
- Patient not in list → Create new order (NOT search)

### 2. Tab Reuse
- `get_reportes` opens tab and keeps it
- `fill`/`fill_many` reuse the same tab
- No redundant navigation

### 3. Auto-Highlight
- `fill` and `fill_many` automatically highlight changes
- Shows `prev → new` badge
- Scrolls to modified field
- No separate highlight tool call needed

### 4. Minimal Tokens
```
7 tools total (removed search)
Short names: fill, hl, ask_user
Short params: e, f, v instead of exam_name, field_name, value

Savings per typical operation: ~60% fewer tokens
```

---

## Typical Complete Flow

```
1. Chat created → Backend fetches orders → sends list to AI
2. User: "Ingresa EMO para Chandi" + image
3. AI finds Chandi in context (NO search)
4. AI: get_reportes(orden="2501181")  
   → Tab opens, data returned, tab stays open
5. AI: fill_many([...])
   → Same tab, fields filled, auto-highlighted
6. AI: ask_user(action="save", msg="...")
   → Frontend shows "waiting for user"
7. User clicks Guardar in browser
8. User tells AI "listo" or sends next request
9. AI continues with next patient
```

---

## If Patient NOT in List

```
1. User: "Ingresa EMO para Martinez, cédula 1234567890"
2. AI checks context → Martinez NOT in orders list
3. AI does NOT search (old orders = old data)
4. AI: create_orden(cedula="1234567890", exams=["EMO"])
5. AI: ask_user(action="save", msg="Creé la orden...")
6. User clicks Guardar
7. User: "listo"
8. AI: get_reportes(orden="NEW_ORDER_NUM")
9. AI: fill_many([...])
10. AI: ask_user(action="save", msg="...")
```
