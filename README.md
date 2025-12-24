# Lab Assistant AI

Sistema de chat con IA para ayudar al personal de laboratorio a ingresar resultados de exámenes en laboratoriofranz.orion-labs.com.

## Características

- 💬 **Chat con IA**: Envía texto, imágenes del cuaderno, o audio con instrucciones
- 🔍 **Extracción automática**: Obtiene lista de órdenes y datos del sitio
- 🛠️ **Herramientas de IA**: 8 herramientas especializadas (get_reportes, fill, add_exam, etc.)
- 📊 **Contexto optimizado**: Formateadores que reducen tokens en ~52%
- 📋 **Revisión de datos**: Tabla editable para verificar datos antes de ejecutar
- 🔒 **Seguro**: El agente NUNCA hace click en "Guardar" - solo el usuario puede

## Requisitos

- Python 3.11+
- Node.js 18+
- Microsoft Edge instalado
- API keys de Gemini

## Instalación

### 1. Clonar y configurar

```bash
git clone <tu-repo>
cd lab-assistant

# Configurar variables de entorno
cp .env.example .env
# Edita .env y agrega tus GEMINI_API_KEYS
```

### 2. Instalar dependencias

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
playwright install      # Instalar drivers de Playwright
cd ..

# Frontend
cd frontend
npm install
cd ..
```

## Ejecución

### Opción 1: Ejecutar todo junto (recomendado)

```bash
python main.py
```

Esto inicia:
- Backend en http://localhost:8000
- Frontend en http://localhost:5173
- Abre Edge con la página del laboratorio

### Opción 2: Ejecutar por separado

**Terminal 1 - Backend:**
```bash
cd backend
venv\Scripts\activate
python run_windows.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## Desarrollo y Testing

### Inspección del sitio

Para ver cómo el código extrae datos de las páginas:

```bash
cd backend
venv\Scripts\activate
python inspect_ordenes.py      # Inspecciona lista de órdenes
python inspect_reportes.py     # Inspecciona página de reportes
python inspect_edit_orden.py   # Inspecciona edición de orden
```

Los scripts guardan HTML en `html_samples/` para análisis offline.

### Tests de extracción (sin Playwright)

Valida los extractores usando archivos HTML guardados:

```bash
cd backend
python test_extractors_static.py
```

### Comparar formatos de contexto

Ver cómo se optimiza el contexto enviado a la IA:

```bash
cd backend
python preview_ai_context.py
```

Muestra comparación OLD vs NEW con ahorro de tokens (~52% reducción).

## Uso

1. Ejecuta `python main.py`
2. Abre http://localhost:5173
3. Inicia sesión en Edge si es necesario
4. Crea un nuevo chat
5. Envía mensaje, imagen o audio
6. Revisa el plan generado
7. Aprueba la ejecución
8. **Haz click en "Guardar" manualmente**

## Arquitectura

```
Usuario (texto/imagen/audio)
       ↓
  Frontend React ←→ Backend FastAPI
       ↓
  Gemini AI (contexto optimizado + herramientas)
       ↓
  Genera tool_calls (get_reportes, fill, etc.)
       ↓
  ToolExecutor ejecuta en Playwright
       ↓
  Usuario hace click en Guardar
```

## Estructura

```
lab-assistant/
├── main.py                      # 🚀 Launcher principal
├── backend/
│   ├── main.py                  # FastAPI app
│   ├── run_windows.py           # Runner para Windows
│   ├── lab_agent.py             # Agente principal
│   ├── gemini_handler.py        # Gemini con rotación de keys
│   ├── browser_manager.py       # Control con Playwright
│   ├── database.py              # SQLite para chats
│   │
│   ├── # Módulos del agente IA
│   ├── extractors.py            # JavaScript extractors por página
│   ├── tools.py                 # 8 herramientas para la IA
│   ├── tool_executor.py         # Ejecuta tool_calls
│   ├── prompts.py               # System prompt + abreviaturas
│   ├── schemas.py               # Validación de respuestas
│   ├── context_formatters.py    # Formateo optimizado (~52% menos tokens)
│   │
│   ├── # Scripts de inspección
│   ├── inspect_ordenes.py       # Inspecciona /ordenes
│   ├── inspect_reportes.py      # Inspecciona /reportes2
│   ├── inspect_edit_orden.py    # Inspecciona /ordenes/{id}/edit
│   │
│   ├── # Testing
│   ├── test_extractors_static.py  # Tests offline con BeautifulSoup
│   ├── preview_ai_context.py      # Comparar formatos OLD vs NEW
│   ├── analyze_html.py            # Utilidad para analizar HTML
│   │
│   ├── html_samples/            # HTML guardado para testing
│   └── site_knowledge/          # JSONs con info de exámenes
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   └── components/
│   └── package.json
│
└── .env
```

## Herramientas de la IA

| Herramienta | Descripción |
|-------------|-------------|
| `get_reportes` | Navega a reportes y extrae campos de exámenes |
| `get_orden` | Navega a editar orden y extrae datos |
| `create_orden` | Navega a crear nueva orden |
| `add_exam` | Agrega examen a una orden |
| `fill` | Llena un campo específico |
| `fill_many` | Llena múltiples campos a la vez |
| `hl` | Resalta campos para el usuario |
| `ask_user` | Pregunta al usuario cuando hay ambigüedad |

## Licencia

MIT
