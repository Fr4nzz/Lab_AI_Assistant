# Coding Plan: Interactive Browser AI Agent with Web UI

## Project Overview

Build an AI-powered browser automation agent that:
1. Accepts user input via web UI (text, image, audio) from any device including phones
2. Uses browser-use library to control a web browser
3. Shows AI plans for user review before execution
4. Allows transcription review and approval before data entry
5. Enables bidirectional communication (AI can ask clarifying questions)
6. Runs on Windows with OpenRouter + Gemini 3 Flash API

---

## Technology Stack

### Backend
- **Python 3.11+** - Main language
- **FastAPI** - REST API + WebSocket server
- **browser-use** - Browser automation with AI
- **OpenRouter API** - LLM access (Gemini 3 Flash)
- **Whisper (openai-whisper or faster-whisper)** - Audio transcription (local)
- **Pillow** - Image processing
- **uvicorn** - ASGI server
- **python-multipart** - File uploads

### Frontend
- **HTML5/CSS3/JavaScript** - No framework (simple, works everywhere)
- **WebSocket** - Real-time bidirectional communication
- **MediaRecorder API** - Audio recording in browser
- **Responsive design** - Works on desktop and mobile

### Storage
- **SQLite** - Session history, conversation logs
- **File system** - Uploaded images, audio files, screenshots

---

## Project Structure

```
laboratorio-agent/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Configuration management
│   ├── requirements.txt           # Python dependencies
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # REST API endpoints
│   │   └── websocket.py           # WebSocket handlers
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── browser_agent.py       # browser-use wrapper
│   │   ├── action_executor.py     # Execute approved actions
│   │   ├── plan_generator.py      # Generate execution plans
│   │   └── state_manager.py       # Track agent state
│   │
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── audio_processor.py     # Whisper transcription
│   │   ├── image_processor.py     # Image handling + OCR context
│   │   └── text_processor.py      # Text preprocessing
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py             # Pydantic models
│   │   └── database.py            # SQLite models
│   │
│   └── utils/
│       ├── __init__.py
│       ├── llm_client.py          # OpenRouter/Gemini client
│       └── logger.py              # Logging setup
│
├── frontend/
│   ├── index.html                 # Main UI page
│   ├── css/
│   │   └── styles.css             # Responsive styles
│   ├── js/
│   │   ├── app.js                 # Main application logic
│   │   ├── websocket.js           # WebSocket client
│   │   ├── audio-recorder.js      # Audio recording
│   │   ├── image-upload.js        # Image upload handling
│   │   └── plan-viewer.js         # Plan review UI
│   └── assets/
│       └── icons/                 # UI icons
│
├── data/
│   ├── uploads/                   # User uploaded files
│   ├── screenshots/               # Browser screenshots
│   └── database.sqlite            # SQLite database
│
├── logs/
│   └── agent.log                  # Application logs
│
├── .env                           # Environment variables
├── .env.example                   # Example env file
├── run.bat                        # Windows startup script
└── README.md                      # Setup instructions
```

---

## Core Components Specification

### 1. Backend API (FastAPI)

#### File: `backend/main.py`
```python
"""
FastAPI application entry point.
- Mount static files for frontend
- Include API routes
- Setup WebSocket endpoint
- Configure CORS for local network access
- Initialize browser-use agent on startup
"""
```

**Key responsibilities:**
- Serve frontend files
- Handle REST API requests
- Manage WebSocket connections
- Initialize and manage browser agent lifecycle

#### File: `backend/api/routes.py`

**REST Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/message` | Send text message to agent |
| POST | `/api/upload/image` | Upload image for processing |
| POST | `/api/upload/audio` | Upload audio for transcription |
| GET | `/api/plan/{plan_id}` | Get current execution plan |
| POST | `/api/plan/{plan_id}/approve` | Approve plan for execution |
| POST | `/api/plan/{plan_id}/reject` | Reject plan with feedback |
| POST | `/api/plan/{plan_id}/edit` | Edit plan before approval |
| GET | `/api/transcription/{id}` | Get transcription for review |
| POST | `/api/transcription/{id}/confirm` | Confirm transcription |
| POST | `/api/transcription/{id}/edit` | Edit transcription |
| GET | `/api/session/history` | Get conversation history |
| GET | `/api/agent/status` | Get agent status |
| POST | `/api/agent/stop` | Stop current agent action |
| GET | `/api/browser/screenshot` | Get current browser screenshot |

#### File: `backend/api/websocket.py`

**WebSocket Events (Server → Client):**
```javascript
{
  "type": "agent_thinking",      // AI is processing
  "type": "plan_ready",          // Plan ready for review
  "type": "transcription_ready", // Transcription ready for review
  "type": "question",            // AI asking user a question
  "type": "action_executing",    // Currently executing action
  "type": "action_complete",     // Action finished
  "type": "error",               // Error occurred
  "type": "browser_update",      // Browser state changed
  "type": "task_complete"        // Task finished
}
```

**WebSocket Events (Client → Server):**
```javascript
{
  "type": "user_message",        // Text message from user
  "type": "answer_question",     // Response to AI question
  "type": "approve_plan",        // Approve execution plan
  "type": "reject_plan",         // Reject with reason
  "type": "confirm_transcription", // Confirm OCR/audio text
  "type": "cancel_task"          // Cancel current operation
}
```

---

### 2. Browser Agent Module

#### File: `backend/agent/browser_agent.py`

```python
"""
Wrapper around browser-use library.

Key Features:
1. Initialize browser-use with OpenRouter/Gemini
2. Custom action hooks for plan generation
3. Intercept actions before execution for approval
4. Capture browser state for UI updates
5. Session persistence for login state
"""

class BrowserAgentWrapper:
    def __init__(self, config):
        """
        Initialize with:
        - OpenRouter API key
        - Model selection (gemini-3-flash-preview)
        - Browser settings (headless=False for visibility)
        - Session persistence path
        """
        pass
    
    async def process_user_request(self, request: UserRequest) -> ExecutionPlan:
        """
        Take user input (text + optional image context) and generate
        a step-by-step execution plan WITHOUT executing it.
        
        Returns plan for user review.
        """
        pass
    
    async def execute_approved_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute a user-approved plan step by step.
        Emit WebSocket events for each step.
        Pause and ask for confirmation before data entry.
        """
        pass
    
    async def ask_user_question(self, question: str, options: List[str] = None) -> str:
        """
        Send question to user via WebSocket and wait for response.
        Used when AI needs clarification.
        """
        pass
    
    async def get_browser_screenshot(self) -> bytes:
        """Return current browser screenshot as PNG bytes."""
        pass
    
    async def get_page_elements(self) -> List[ElementInfo]:
        """Get interactive elements from current page for context."""
        pass
```

#### File: `backend/agent/plan_generator.py`

```python
"""
Generate human-readable execution plans from AI intentions.

Plan Structure:
{
  "plan_id": "uuid",
  "task_summary": "Add lab results for patient Juan Perez",
  "steps": [
    {
      "step_number": 1,
      "action": "navigate",
      "description": "Navigate to patient search page",
      "details": {"url": "..."},
      "requires_approval": false
    },
    {
      "step_number": 2,
      "action": "input_text",
      "description": "Enter patient name in search field",
      "details": {"field": "search", "value": "Juan Perez"},
      "requires_approval": false
    },
    {
      "step_number": 3,
      "action": "input_data",
      "description": "Enter lab results",
      "details": {
        "data_to_enter": [
          {"field": "Hemoglobina", "value": "14.5", "unit": "g/dL"},
          {"field": "Glucosa", "value": "95", "unit": "mg/dL"}
        ]
      },
      "requires_approval": true  // MUST be approved before execution
    }
  ],
  "extracted_data": {
    "from_image": true,
    "transcription": "...",
    "parsed_values": {...}
  },
  "confidence_score": 0.92,
  "warnings": ["Verify hemoglobin value - unusual reading"]
}
"""
```

#### File: `backend/agent/state_manager.py`

```python
"""
Manage agent state throughout execution.

States:
- IDLE: Waiting for user input
- PROCESSING: Analyzing user request
- AWAITING_PLAN_APPROVAL: Plan generated, waiting for user
- AWAITING_TRANSCRIPTION_REVIEW: OCR/audio done, needs confirmation
- AWAITING_USER_RESPONSE: AI asked a question
- EXECUTING: Running approved actions
- PAUSED: Execution paused for approval
- ERROR: Error state
- COMPLETED: Task finished
"""
```

---

### 3. Processors Module

#### File: `backend/processors/audio_processor.py`

```python
"""
Audio transcription using Whisper.

Features:
- Accept audio uploads (webm, mp3, wav, m4a)
- Transcribe using faster-whisper (GPU if available, CPU fallback)
- Support Spanish language primarily
- Return timestamped transcription for review
"""

class AudioProcessor:
    def __init__(self, model_size: str = "base"):
        """
        Initialize Whisper model.
        Options: tiny, base, small, medium, large
        Recommend 'base' for balance of speed/accuracy on Windows
        """
        pass
    
    async def transcribe(self, audio_path: str, language: str = "es") -> Transcription:
        """
        Transcribe audio file.
        Returns structured transcription with confidence scores.
        """
        pass
```

#### File: `backend/processors/image_processor.py`

```python
"""
Image processing for handwritten lab results.

Features:
- Accept image uploads (jpg, png, heic)
- Resize/optimize for API submission
- Send to Gemini Vision for OCR + structured extraction
- Parse handwritten lab values into structured data
"""

class ImageProcessor:
    def __init__(self, llm_client):
        """Initialize with LLM client for vision processing."""
        pass
    
    async def extract_lab_results(self, image_path: str) -> LabResultsExtraction:
        """
        Use Gemini Vision to:
        1. OCR the handwritten text
        2. Identify lab test names and values
        3. Structure into parseable format
        4. Flag uncertain readings for review
        """
        pass
    
    async def extract_text_only(self, image_path: str) -> str:
        """Simple OCR without lab-specific parsing."""
        pass
```

---

### 4. Frontend Specification

#### File: `frontend/index.html`

```html
<!--
Main UI Structure:
1. Header with status indicator
2. Chat/conversation area (scrollable)
3. Input area (text, image, audio buttons)
4. Plan review modal
5. Transcription review modal
6. Browser preview panel (optional, shows screenshot)
-->
```

**UI Sections:**

```
┌─────────────────────────────────────────────────────────────┐
│  🤖 Lab Agent        [Status: Connected] [Agent: Idle]      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 Conversation Area                    │   │
│  │                                                     │   │
│  │  [User]: Add these lab results for patient...      │   │
│  │  [Image thumbnail]                                  │   │
│  │                                                     │   │
│  │  [Agent]: I've analyzed the image. Here's what     │   │
│  │  I found:                                          │   │
│  │  - Hemoglobina: 14.5 g/dL                         │   │
│  │  - Glucosa: 95 mg/dL                              │   │
│  │  [Review Transcription Button]                     │   │
│  │                                                     │   │
│  │  [Agent]: Here's my plan:                          │   │
│  │  1. Navigate to patient search                     │   │
│  │  2. Search for "Juan Perez"                        │   │
│  │  3. Enter lab results                              │   │
│  │  [Review Plan Button]                              │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [📷] [🎤] │  Type your message...          │ [Send] │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### File: `frontend/js/app.js`

```javascript
/**
 * Main application controller.
 * 
 * Responsibilities:
 * - Initialize WebSocket connection
 * - Handle user input (text, image, audio)
 * - Render conversation messages
 * - Show/hide modals for plan and transcription review
 * - Handle AI questions with response UI
 * - Update agent status indicator
 */
```

#### File: `frontend/js/audio-recorder.js`

```javascript
/**
 * Audio recording using MediaRecorder API.
 * 
 * Features:
 * - Push-to-talk or toggle recording
 * - Visual feedback (recording indicator)
 * - Auto-stop after silence or max duration
 * - Convert to compatible format for upload
 * - Works on mobile browsers
 */
```

#### File: `frontend/js/plan-viewer.js`

```javascript
/**
 * Plan review UI component.
 * 
 * Features:
 * - Display step-by-step plan
 * - Highlight steps requiring approval
 * - Show data that will be entered
 * - Edit capability for individual fields
 * - Approve/Reject buttons
 * - Progress indicator during execution
 */
```

---

### 5. Data Models

#### File: `backend/models/schemas.py`

```python
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class AgentStatus(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    AWAITING_TRANSCRIPTION_REVIEW = "awaiting_transcription_review"
    AWAITING_USER_RESPONSE = "awaiting_user_response"
    EXECUTING = "executing"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"

class UserMessage(BaseModel):
    content: str
    image_id: Optional[str] = None
    audio_id: Optional[str] = None
    timestamp: datetime

class PlanStep(BaseModel):
    step_number: int
    action: str
    description: str
    details: Dict[str, Any]
    requires_approval: bool
    status: str = "pending"  # pending, executing, completed, failed

class ExecutionPlan(BaseModel):
    plan_id: str
    task_summary: str
    steps: List[PlanStep]
    extracted_data: Optional[Dict[str, Any]] = None
    confidence_score: float
    warnings: List[str] = []
    created_at: datetime
    status: str = "pending_approval"

class Transcription(BaseModel):
    transcription_id: str
    source_type: str  # "audio" or "image"
    original_text: str
    parsed_data: Optional[Dict[str, Any]] = None
    confidence_scores: Dict[str, float] = {}
    needs_review: bool = True
    user_edited: bool = False
    final_text: Optional[str] = None

class AIQuestion(BaseModel):
    question_id: str
    question_text: str
    options: Optional[List[str]] = None  # If multiple choice
    context: Optional[str] = None
    awaiting_response: bool = True

class LabResult(BaseModel):
    test_name: str
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = None  # "high", "low", "normal", "uncertain"

class WebSocketMessage(BaseModel):
    type: str
    payload: Dict[str, Any]
    timestamp: datetime
```

---

## Implementation Phases

### Phase 1: Project Setup & Basic Backend (Day 1)

**Tasks:**
1. Create project directory structure
2. Setup Python virtual environment
3. Install dependencies (FastAPI, browser-use, etc.)
4. Create configuration management (.env)
5. Setup basic FastAPI app with CORS
6. Create static file serving for frontend
7. Implement basic health check endpoint
8. Setup logging

**Deliverables:**
- Working FastAPI server
- Can serve static HTML
- Basic configuration loading
- Logging working

**Files to create:**
- `backend/main.py`
- `backend/config.py`
- `backend/requirements.txt`
- `backend/utils/logger.py`
- `.env.example`
- `run.bat`

---

### Phase 2: Frontend Foundation (Day 1-2)

**Tasks:**
1. Create responsive HTML layout
2. Implement CSS styling (mobile-first)
3. Create WebSocket client module
4. Implement chat/conversation UI
5. Create text input with send functionality
6. Create image upload button and preview
7. Create audio recording UI
8. Create status indicator component

**Deliverables:**
- Fully responsive UI
- WebSocket connection (mocked)
- Can send text messages
- Can select/preview images
- Audio recording works

**Files to create:**
- `frontend/index.html`
- `frontend/css/styles.css`
- `frontend/js/app.js`
- `frontend/js/websocket.js`
- `frontend/js/audio-recorder.js`
- `frontend/js/image-upload.js`

---

### Phase 3: WebSocket & Real-time Communication (Day 2)

**Tasks:**
1. Implement WebSocket endpoint in FastAPI
2. Create connection manager for multiple clients
3. Implement message routing (server ↔ client)
4. Create message queue for agent communication
5. Implement reconnection logic on frontend
6. Test bidirectional communication

**Deliverables:**
- WebSocket fully functional
- Messages flow both directions
- Multiple clients supported
- Reconnection works

**Files to create:**
- `backend/api/websocket.py`
- Update `frontend/js/websocket.js`

---

### Phase 4: Audio & Image Processing (Day 2-3)

**Tasks:**
1. Install and configure Whisper
2. Implement audio upload endpoint
3. Implement audio transcription
4. Implement image upload endpoint
5. Create Gemini Vision integration for OCR
6. Create lab results extraction prompt
7. Implement transcription review flow

**Deliverables:**
- Audio transcription working
- Image OCR working
- Lab results extracted from images
- Transcription sent to frontend for review

**Files to create:**
- `backend/processors/audio_processor.py`
- `backend/processors/image_processor.py`
- `backend/utils/llm_client.py`
- `backend/api/routes.py` (upload endpoints)

---

### Phase 5: Browser Agent Integration (Day 3-4)

**Tasks:**
1. Implement browser-use wrapper
2. Configure OpenRouter + Gemini 3 Flash
3. Implement session persistence
4. Create plan generation (without execution)
5. Implement action interception
6. Create browser screenshot capture
7. Implement element extraction for context

**Deliverables:**
- browser-use initialized and working
- Plans generated from user requests
- Browser screenshots available
- Actions can be intercepted

**Files to create:**
- `backend/agent/browser_agent.py`
- `backend/agent/plan_generator.py`
- `backend/agent/state_manager.py`

---

### Phase 6: Plan Review System (Day 4)

**Tasks:**
1. Create plan review modal in frontend
2. Implement plan display with step details
3. Add data preview for data entry steps
4. Implement edit functionality
5. Add approve/reject buttons
6. Connect to WebSocket events
7. Implement plan status updates

**Deliverables:**
- Plan modal fully functional
- Can view all steps
- Can edit data before approval
- Can approve or reject
- Status updates in real-time

**Files to create/update:**
- `frontend/js/plan-viewer.js`
- Update `frontend/index.html` (modal)
- Update `frontend/css/styles.css`

---

### Phase 7: Execution Engine (Day 4-5)

**Tasks:**
1. Implement step-by-step execution
2. Add pause points for approval
3. Implement progress updates via WebSocket
4. Create rollback capability
5. Handle errors gracefully
6. Implement stop/cancel functionality

**Deliverables:**
- Agent executes approved plans
- Pauses for data entry confirmation
- Real-time progress updates
- Can stop execution
- Errors handled gracefully

**Files to create:**
- `backend/agent/action_executor.py`
- Update `backend/agent/browser_agent.py`

---

### Phase 8: AI Question System (Day 5)

**Tasks:**
1. Implement AI question generation
2. Create question UI component (text response)
3. Create multiple choice UI (button selection)
4. Implement voice response option
5. Route answers back to agent
6. Integrate with execution flow

**Deliverables:**
- AI can ask questions
- User can respond via text, voice, or selection
- Answers influence agent behavior

**Files to create/update:**
- Update `frontend/js/app.js` (question UI)
- Update `backend/agent/browser_agent.py`

---

### Phase 9: Session & History (Day 5-6)

**Tasks:**
1. Setup SQLite database
2. Create conversation history storage
3. Implement session persistence
4. Create history endpoint
5. Add history view in frontend
6. Implement conversation resume

**Deliverables:**
- Conversations persisted
- History viewable
- Can reference past conversations
- Browser session persists login

**Files to create:**
- `backend/models/database.py`
- Update `backend/api/routes.py`

---

### Phase 10: Testing & Polish (Day 6)

**Tasks:**
1. End-to-end testing
2. Mobile testing (phone browser)
3. Error handling improvements
4. Loading states and feedback
5. Performance optimization
6. Documentation

**Deliverables:**
- All features working
- Works on mobile
- Proper error messages
- Good user feedback
- README with setup instructions

---

## Configuration

### File: `.env.example`

```bash
# OpenRouter API
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=google/gemini-3-flash-preview

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Browser Settings
BROWSER_HEADLESS=false
BROWSER_USER_DATA_DIR=./data/browser_profile
TARGET_URL=https://laboratoriofranz.orion-labs.com/

# Whisper Settings
WHISPER_MODEL=base
WHISPER_LANGUAGE=es

# Storage
UPLOAD_DIR=./data/uploads
SCREENSHOT_DIR=./data/screenshots
DATABASE_PATH=./data/database.sqlite

# Security (for local network access)
ALLOWED_ORIGINS=*
```

### File: `backend/requirements.txt`

```
# Core
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
python-dotenv>=1.0.0
pydantic>=2.5.0

# Browser Automation
browser-use>=0.1.40
playwright>=1.40.0

# LLM
langchain-openai>=0.1.0
openai>=1.12.0

# Audio Processing
faster-whisper>=0.10.0
# OR: openai-whisper>=20231117

# Image Processing
Pillow>=10.0.0

# Database
aiosqlite>=0.19.0

# Utilities
aiofiles>=23.2.0
websockets>=12.0
```

### File: `run.bat`

```batch
@echo off
echo Starting Lab Agent...

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Set environment variables
set HOST=0.0.0.0
set PORT=8000

REM Start the server
echo Server starting at http://localhost:%PORT%
echo Access from other devices at http://<your-ip>:%PORT%
python -m uvicorn backend.main:app --host %HOST% --port %PORT% --reload

pause
```

---

## Key Implementation Details

### 1. OpenRouter + Gemini 3 Flash Setup

```python
# backend/utils/llm_client.py
from browser_use import ChatOpenAI
import os

def get_llm_client():
    return ChatOpenAI(
        model=os.getenv('OPENROUTER_MODEL', 'google/gemini-3-flash-preview'),
        base_url='https://openrouter.ai/api/v1',
        api_key=os.getenv('OPENROUTER_API_KEY'),
    )
```

### 2. Plan Generation Prompt Template

```python
PLAN_GENERATION_PROMPT = """
You are a browser automation assistant for a clinical laboratory system.

Given the user's request and any provided images/transcriptions, create a detailed execution plan.

CRITICAL RULES:
1. Generate a step-by-step plan but DO NOT execute anything yet
2. For any data entry steps, mark requires_approval=true
3. Extract and structure all data that will be entered
4. Flag any uncertain values or potential issues
5. Always confirm patient identity before data entry

User Request: {user_request}

Image Transcription (if any): {image_transcription}

Audio Transcription (if any): {audio_transcription}

Current Page Context: {page_context}

Return a JSON execution plan following this structure:
{plan_schema}
"""
```

### 3. Mobile-Friendly Audio Recording

```javascript
// frontend/js/audio-recorder.js
class AudioRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
    }
    
    async start() {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                channelCount: 1,
                sampleRate: 16000,
                echoCancellation: true,
                noiseSuppression: true
            } 
        });
        
        // Use webm for broad compatibility
        this.mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        this.audioChunks = [];
        this.mediaRecorder.ondataavailable = (e) => {
            this.audioChunks.push(e.data);
        };
        
        this.mediaRecorder.start();
    }
    
    async stop() {
        return new Promise((resolve) => {
            this.mediaRecorder.onstop = () => {
                const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
                resolve(blob);
            };
            this.mediaRecorder.stop();
        });
    }
}
```

### 4. Intercepting browser-use Actions

```python
# backend/agent/browser_agent.py
from browser_use import Agent, Browser
from browser_use.agent.views import ActionResult

class BrowserAgentWrapper:
    def __init__(self, config, websocket_manager):
        self.config = config
        self.ws_manager = websocket_manager
        self.pending_approval = None
        
    async def process_with_approval(self, task: str, context: dict):
        """
        Process task but intercept before data entry.
        """
        # First, generate plan without execution
        plan = await self._generate_plan(task, context)
        
        # Send plan for approval
        await self.ws_manager.broadcast({
            "type": "plan_ready",
            "payload": plan.dict()
        })
        
        # Wait for approval
        self.pending_approval = asyncio.Event()
        await self.pending_approval.wait()
        
        # Execute approved plan
        if self.approved_plan:
            return await self._execute_plan(self.approved_plan)
        else:
            return {"status": "rejected", "reason": self.rejection_reason}
```

---

## Testing Checklist

### Functional Tests
- [ ] Text message sent and received
- [ ] Image upload and OCR extraction
- [ ] Audio recording and transcription
- [ ] Plan generation from request
- [ ] Plan approval flow
- [ ] Plan rejection flow
- [ ] Plan editing before approval
- [ ] Transcription review and edit
- [ ] AI question display
- [ ] AI question response (text)
- [ ] AI question response (voice)
- [ ] AI question response (selection)
- [ ] Agent execution with progress
- [ ] Agent pause for confirmation
- [ ] Agent stop/cancel
- [ ] Browser screenshot display
- [ ] Session persistence
- [ ] History retrieval

### Cross-Device Tests
- [ ] Desktop Chrome
- [ ] Desktop Firefox
- [ ] Mobile Chrome (Android)
- [ ] Mobile Safari (iOS)
- [ ] Tablet

### Error Handling Tests
- [ ] Network disconnection
- [ ] API errors
- [ ] Invalid file uploads
- [ ] Browser crashes
- [ ] Timeout handling

---

## Security Considerations

1. **Local Network Only**: By default, bind to local network only
2. **No Authentication**: For home/office use; add if exposing publicly
3. **File Validation**: Validate uploaded file types and sizes
4. **Input Sanitization**: Sanitize user inputs
5. **API Key Protection**: Never expose API keys to frontend
6. **HTTPS**: Use HTTPS if accessing over internet (use ngrok or similar)

---

## Future Enhancements

1. **Multi-language Support**: Add English, Portuguese
2. **Voice Output**: AI speaks responses (TTS)
3. **Multiple Browser Tabs**: Handle multiple workflows
4. **Batch Processing**: Process multiple lab results
5. **Report Generation**: Generate PDF reports
6. **User Authentication**: Login system for multiple users
7. **Audit Log**: Track all actions for compliance
8. **Offline Mode**: Queue tasks when offline

---

## Getting Started Command for Claude Code

```
Create the laboratorio-agent project following the coding plan. Start with Phase 1:

1. Create the project directory structure as specified
2. Create backend/requirements.txt with all dependencies
3. Create backend/config.py for configuration management
4. Create backend/main.py with FastAPI setup, CORS, and static file serving
5. Create backend/utils/logger.py for logging
6. Create .env.example with all configuration options
7. Create run.bat for Windows startup
8. Create a minimal frontend/index.html that shows "Lab Agent - Loading..."

Use Python 3.11+ features. Make sure the server starts and serves the frontend correctly.
```
