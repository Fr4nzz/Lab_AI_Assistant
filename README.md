# Lab Assistant AI

Sistema de chat con IA para ayudar al personal de laboratorio a ingresar resultados de exámenes en laboratoriofranz.orion-labs.com.

## Características

- 💬 **Chat con IA**: Envía texto, imágenes del cuaderno, o audio con instrucciones
- 🔍 **Extracción automática**: Obtiene lista de órdenes y datos del sitio
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

## Inspección del sitio (desarrollo)

Para ver cómo el código extrae datos de las páginas:

```bash
cd backend
venv\Scripts\activate
python inspect_ordenes.py
```

Esto genera `inspeccion_ordenes.json` con la estructura de la página.

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
  Gemini AI (contexto: órdenes actuales + mensaje)
       ↓
  Genera plan de acciones
       ↓
  Usuario revisa y aprueba
       ↓
  Playwright ejecuta acciones
       ↓
  Usuario hace click en Guardar
```

## Estructura

```
lab-assistant/
├── main.py                  # 🚀 Launcher principal
├── backend/
│   ├── main.py              # FastAPI app
│   ├── run_windows.py       # Runner para Windows
│   ├── inspect_ordenes.py   # Script de inspección
│   ├── browser_manager.py   # Control con Playwright
│   ├── gemini_handler.py    # Gemini con rotación de keys
│   ├── lab_agent.py         # Lógica del agente
│   └── site_knowledge/      # JSONs con info de exámenes
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   └── components/
│   └── package.json
└── .env
```

## Licencia

MIT
