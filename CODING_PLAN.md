# Lab Assistant AI Agent - Coding Plan

## Project Overview

Build an AI agent that helps laboratory staff enter exam results into `laboratoriofranz.orion-labs.com`. Users send text/image/audio via a chat interface. Gemini 3 Flash interprets input, extracts data, and controls the browser. User reviews before execution.

**Architecture**: Single Gemini AI agent with full context. Browser-use provides DOM extraction and Playwright controls—NOT its built-in AI agent.

```
User Input (text/image/audio)
         ↓
    React Frontend ←→ FastAPI Backend
         ↓
Browser State + Chat History + User Input → Gemini 3 Flash
         ↓
JSON Actions (click, type, navigate)
         ↓
Deterministic Executor (Playwright via browser-use primitives)
         ↓
Browser
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + Vite + TypeScript |
| Backend | FastAPI (Python) |
| AI | Gemini 3 Flash via google-genai SDK |
| Browser Control | browser-use (as toolkit) + Playwright |
| Database | SQLite (chat history, sessions) |

---

## Phase 1: Project Setup

### 1.1 Create project structure

```
lab-assistant/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Settings, API keys
│   ├── database.py             # SQLite models
│   ├── browser_manager.py      # Browser control
│   ├── gemini_agent.py         # AI agent logic
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── PlanReview.tsx
│   │   │   └── DataTable.tsx
│   │   └── api/
│   │       └── client.ts
│   ├── package.json
│   └── vite.config.ts
└── .env
```

### 1.2 Backend dependencies (requirements.txt)

```
fastapi
uvicorn
python-multipart
google-genai
browser-use
playwright
sqlalchemy
python-dotenv
websockets
```

### 1.3 Frontend setup

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install axios
```

### 1.4 Environment variables (.env)

```
GEMINI_API_KEY=your_key
TARGET_URL=https://laboratoriofranz.orion-labs.com/
```

---

## Phase 2: Browser Manager

Create `backend/browser_manager.py` - wraps browser-use for DOM extraction and action execution.

### 2.1 Core class

```python
from browser_use import Browser
from playwright.async_api import Page
import asyncio

class BrowserManager:
    def __init__(self):
        self.browser = None
        self.page = None
    
    async def start(self, headless=False):
        self.browser = Browser(
            headless=headless,
            keep_alive=True,
            user_data_dir="./browser_data"  # Persist sessions
        )
        context = await self.browser.get_context()
        self.page = await context.new_page()
    
    async def navigate(self, url: str):
        await self.page.goto(url, timeout=60000)
        await self.page.wait_for_load_state("networkidle")
    
    async def get_state(self) -> dict:
        """Extract current browser state for AI context"""
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "elements": await self._extract_elements()
        }
    
    async def _extract_elements(self) -> list:
        """Get all interactive elements with indices"""
        script = """
        () => {
            const elements = [];
            const interactables = document.querySelectorAll(
                'button, a, input, select, textarea, [onclick], [role="button"]'
            );
            interactables.forEach((el, idx) => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    elements.push({
                        index: idx,
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText?.slice(0, 100) || '',
                        placeholder: el.placeholder || '',
                        id: el.id || '',
                        name: el.name || '',
                        type: el.type || '',
                        value: el.value || ''
                    });
                }
            });
            return elements;
        }
        """
        return await self.page.evaluate(script)
    
    async def execute_action(self, action: dict):
        """Execute a single action from Gemini"""
        action_type = action.get("action")
        
        if action_type == "click":
            selector = f":nth-match(button, a, input, select, textarea, [onclick], [role='button'], {action['index'] + 1})"
            await self.page.locator(selector).click()
        
        elif action_type == "type":
            selector = f":nth-match(input, textarea, {action['index'] + 1})"
            element = self.page.locator(selector)
            if action.get("clear", True):
                await element.fill("")
            await element.fill(action["text"])
        
        elif action_type == "select":
            selector = f":nth-match(select, {action['index'] + 1})"
            await self.page.locator(selector).select_option(value=action["value"])
        
        elif action_type == "navigate":
            await self.navigate(action["url"])
        
        elif action_type == "wait":
            await asyncio.sleep(action.get("seconds", 1))
    
    async def close(self):
        if self.browser:
            await self.browser.close()
```

### 2.2 Key points

- Use Playwright directly for action execution (deterministic, no AI)
- `get_state()` returns JSON that goes to Gemini as context
- `execute_action()` handles Gemini's JSON commands
- Session persistence via `user_data_dir`

---

## Phase 3: Gemini Agent

Create `backend/gemini_agent.py` - single AI agent with full context.

### 3.1 Core class

```python
from google import genai
from google.genai import types
import json

class GeminiAgent:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash-preview-05-20"
    
    def build_context(
        self,
        user_message: str,
        browser_state: dict,
        chat_history: list,
        attachments: list = None  # base64 images or audio
    ) -> list:
        """Build full context for Gemini"""
        
        system_prompt = f"""You are a lab assistant AI. Help users enter exam results into the laboratory system.

Current browser state:
- URL: {browser_state['url']}
- Page: {browser_state['title']}
- Available elements:
{self._format_elements(browser_state['elements'])}

Instructions:
1. Analyze user input (text, images of handwritten results, or audio)
2. Extract patient name, exam type, and values
3. Return a JSON plan with actions to execute

Response format (JSON only):
{{
    "understanding": "What you understood from the input",
    "extracted_data": [
        {{
            "patient": "Name",
            "exam": "Exam type",
            "fields": [
                {{"field": "Field name", "value": "Value"}}
            ]
        }}
    ],
    "plan": {{
        "steps": [
            {{"action": "navigate", "url": "..."}},
            {{"action": "click", "index": 5}},
            {{"action": "type", "index": 3, "text": "..."}},
            {{"action": "select", "index": 7, "value": "..."}},
            {{"action": "wait", "seconds": 1}}
        ]
    }},
    "question": null  // Or ask user for clarification
}}"""

        contents = [system_prompt]
        
        # Add chat history (slim version)
        for msg in chat_history[-10:]:  # Last 10 messages
            contents.append(f"{msg['role']}: {msg['content']}")
        
        # Add attachments (images/audio)
        if attachments:
            for att in attachments:
                contents.append(att)  # Gemini handles multimodal natively
        
        contents.append(f"User: {user_message}")
        
        return contents
    
    def _format_elements(self, elements: list) -> str:
        """Format elements for prompt"""
        lines = []
        for el in elements[:50]:  # Limit to 50 most relevant
            desc = f"[{el['index']}] <{el['tag']}>"
            if el['text']:
                desc += f" \"{el['text'][:50]}\""
            if el['placeholder']:
                desc += f" placeholder=\"{el['placeholder']}\""
            if el['id']:
                desc += f" id=\"{el['id']}\""
            lines.append(desc)
        return "\n".join(lines)
    
    async def process(
        self,
        user_message: str,
        browser_state: dict,
        chat_history: list,
        attachments: list = None
    ) -> dict:
        """Send to Gemini and parse response"""
        
        contents = self.build_context(
            user_message, browser_state, chat_history, attachments
        )
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        text = response.candidates[0].content.parts[0].text
        return json.loads(text)
```

### 3.2 Key points

- Single model call with ALL context (browser state, history, attachments)
- `response_mime_type="application/json"` ensures structured output
- Returns extracted data + action plan for user review
- Supports multimodal: text, images, audio sent directly to Gemini

---

## Phase 4: FastAPI Backend

Create `backend/main.py` - API endpoints and WebSocket for real-time updates.

### 4.1 Core endpoints

```python
from fastapi import FastAPI, UploadFile, File, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import asyncio

from browser_manager import BrowserManager
from gemini_agent import GeminiAgent
from database import ChatDB

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

browser = BrowserManager()
agent = GeminiAgent(api_key=os.getenv("GEMINI_API_KEY"))
db = ChatDB()

@app.on_event("startup")
async def startup():
    await browser.start(headless=False)
    await browser.navigate(os.getenv("TARGET_URL"))

@app.on_event("shutdown")
async def shutdown():
    await browser.close()

class MessageRequest(BaseModel):
    chat_id: str
    message: str

@app.post("/api/chat")
async def send_message(request: MessageRequest, files: list[UploadFile] = None):
    # Get chat history
    history = db.get_history(request.chat_id)
    
    # Process attachments
    attachments = []
    if files:
        for f in files:
            content = await f.read()
            b64 = base64.b64encode(content).decode()
            attachments.append({
                "type": f.content_type,
                "data": b64
            })
    
    # Get browser state
    state = await browser.get_state()
    
    # Process with Gemini
    result = await agent.process(
        user_message=request.message,
        browser_state=state,
        chat_history=history,
        attachments=attachments
    )
    
    # Save to history
    db.add_message(request.chat_id, "user", request.message)
    db.add_message(request.chat_id, "assistant", result["understanding"])
    
    return {
        "understanding": result["understanding"],
        "extracted_data": result["extracted_data"],
        "plan": result["plan"],
        "question": result.get("question")
    }

@app.post("/api/execute")
async def execute_plan(plan: dict):
    """Execute approved plan"""
    results = []
    for step in plan["steps"]:
        await browser.execute_action(step)
        state = await browser.get_state()
        results.append({"step": step, "new_url": state["url"]})
        await asyncio.sleep(0.5)  # Small delay between actions
    return {"success": True, "results": results}

@app.get("/api/chats")
async def list_chats():
    return db.get_all_chats()

@app.post("/api/chats")
async def create_chat():
    return db.create_chat()

@app.get("/api/browser/state")
async def get_browser_state():
    return await browser.get_state()
```

### 4.2 Database (backend/database.py)

```python
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import uuid
from datetime import datetime

Base = declarative_base()
engine = create_engine("sqlite:///chats.db")
Session = sessionmaker(bind=engine)

class Chat(Base):
    __tablename__ = "chats"
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    title = Column(String, default="New Chat")

class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    chat_id = Column(String)
    role = Column(String)  # user, assistant
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

class ChatDB:
    def create_chat(self):
        session = Session()
        chat = Chat(id=str(uuid.uuid4()))
        session.add(chat)
        session.commit()
        return {"id": chat.id}
    
    def get_history(self, chat_id: str) -> list:
        session = Session()
        messages = session.query(Message).filter_by(chat_id=chat_id).order_by(Message.created_at).all()
        return [{"role": m.role, "content": m.content} for m in messages]
    
    def add_message(self, chat_id: str, role: str, content: str):
        session = Session()
        msg = Message(id=str(uuid.uuid4()), chat_id=chat_id, role=role, content=content)
        session.add(msg)
        session.commit()
    
    def get_all_chats(self) -> list:
        session = Session()
        chats = session.query(Chat).order_by(Chat.created_at.desc()).all()
        return [{"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()} for c in chats]
```

---

## Phase 5: React Frontend

### 5.1 Main App (frontend/src/App.tsx)

```tsx
import { useState, useEffect } from 'react'
import ChatInterface from './components/ChatInterface'
import ChatList from './components/ChatList'
import './App.css'

function App() {
  const [currentChatId, setCurrentChatId] = useState<string | null>(null)
  const [chats, setChats] = useState<any[]>([])

  useEffect(() => {
    loadChats()
  }, [])

  const loadChats = async () => {
    const res = await fetch('http://localhost:8000/api/chats')
    const data = await res.json()
    setChats(data)
  }

  const createChat = async () => {
    const res = await fetch('http://localhost:8000/api/chats', { method: 'POST' })
    const data = await res.json()
    setCurrentChatId(data.id)
    loadChats()
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <button onClick={createChat}>New Chat</button>
        <ChatList chats={chats} onSelect={setCurrentChatId} selected={currentChatId} />
      </aside>
      <main className="main">
        {currentChatId ? (
          <ChatInterface chatId={currentChatId} />
        ) : (
          <div className="placeholder">Select or create a chat</div>
        )}
      </main>
    </div>
  )
}

export default App
```

### 5.2 Chat Interface (frontend/src/components/ChatInterface.tsx)

```tsx
import { useState, useRef } from 'react'
import PlanReview from './PlanReview'
import DataTable from './DataTable'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  chatId: string
}

export default function ChatInterface({ chatId }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [pendingPlan, setPendingPlan] = useState<any>(null)
  const [extractedData, setExtractedData] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const sendMessage = async () => {
    if (!input.trim() && files.length === 0) return
    
    setIsLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: input }])
    
    const formData = new FormData()
    formData.append('chat_id', chatId)
    formData.append('message', input)
    files.forEach(f => formData.append('files', f))
    
    const res = await fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      body: formData
    })
    const data = await res.json()
    
    setMessages(prev => [...prev, { role: 'assistant', content: data.understanding }])
    
    if (data.extracted_data?.length > 0) {
      setExtractedData(data.extracted_data)
    }
    
    if (data.plan) {
      setPendingPlan(data.plan)
    }
    
    if (data.question) {
      setMessages(prev => [...prev, { role: 'assistant', content: data.question }])
    }
    
    setInput('')
    setFiles([])
    setIsLoading(false)
  }

  const executePlan = async (editedData: any[]) => {
    // Update plan with edited data if needed
    const res = await fetch('http://localhost:8000/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...pendingPlan, data: editedData })
    })
    const result = await res.json()
    
    setMessages(prev => [...prev, { 
      role: 'assistant', 
      content: result.success ? 'Plan executed successfully!' : 'Execution failed' 
    }])
    setPendingPlan(null)
    setExtractedData([])
  }

  return (
    <div className="chat-interface">
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {isLoading && <div className="message loading">Thinking...</div>}
      </div>
      
      {extractedData.length > 0 && (
        <DataTable 
          data={extractedData} 
          onChange={setExtractedData}
        />
      )}
      
      {pendingPlan && (
        <PlanReview 
          plan={pendingPlan}
          onApprove={() => executePlan(extractedData)}
          onCancel={() => setPendingPlan(null)}
        />
      )}
      
      <div className="input-area">
        <input
          type="file"
          ref={fileInputRef}
          multiple
          accept="image/*,audio/*"
          onChange={e => setFiles(Array.from(e.target.files || []))}
          style={{ display: 'none' }}
        />
        <button onClick={() => fileInputRef.current?.click()}>📎</button>
        {files.length > 0 && <span>{files.length} file(s)</span>}
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyPress={e => e.key === 'Enter' && sendMessage()}
          placeholder="Type a message or attach files..."
        />
        <button onClick={sendMessage} disabled={isLoading}>Send</button>
      </div>
    </div>
  )
}
```

### 5.3 Data Table (frontend/src/components/DataTable.tsx)

```tsx
interface DataEntry {
  patient: string
  exam: string
  fields: { field: string; value: string }[]
}

interface Props {
  data: DataEntry[]
  onChange: (data: DataEntry[]) => void
}

export default function DataTable({ data, onChange }: Props) {
  const updateField = (patientIdx: number, fieldIdx: number, newValue: string) => {
    const updated = [...data]
    updated[patientIdx].fields[fieldIdx].value = newValue
    onChange(updated)
  }

  return (
    <div className="data-table">
      <h3>Extracted Data (Review & Edit)</h3>
      {data.map((entry, pi) => (
        <div key={pi} className="patient-entry">
          <h4>{entry.patient} - {entry.exam}</h4>
          <table>
            <thead>
              <tr><th>Field</th><th>Value</th></tr>
            </thead>
            <tbody>
              {entry.fields.map((f, fi) => (
                <tr key={fi}>
                  <td>{f.field}</td>
                  <td>
                    <input
                      type="text"
                      value={f.value}
                      onChange={e => updateField(pi, fi, e.target.value)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}
```

### 5.4 Plan Review (frontend/src/components/PlanReview.tsx)

```tsx
interface Props {
  plan: {
    steps: { action: string; index?: number; text?: string; url?: string }[]
  }
  onApprove: () => void
  onCancel: () => void
}

export default function PlanReview({ plan, onApprove, onCancel }: Props) {
  return (
    <div className="plan-review">
      <h3>Execution Plan</h3>
      <ol>
        {plan.steps.map((step, i) => (
          <li key={i}>
            {step.action === 'click' && `Click element #${step.index}`}
            {step.action === 'type' && `Type "${step.text}" in element #${step.index}`}
            {step.action === 'navigate' && `Navigate to ${step.url}`}
            {step.action === 'select' && `Select "${step.value}" in dropdown #${step.index}`}
            {step.action === 'wait' && `Wait ${step.seconds}s`}
          </li>
        ))}
      </ol>
      <div className="actions">
        <button onClick={onApprove}>Execute</button>
        <button onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}
```

### 5.5 Styles (frontend/src/App.css)

```css
* { box-sizing: border-box; margin: 0; padding: 0; }

.app {
  display: flex;
  height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}

.sidebar {
  width: 250px;
  background: #1a1a2e;
  color: white;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sidebar button {
  background: #4a4a8a;
  color: white;
  border: none;
  padding: 0.75rem;
  border-radius: 8px;
  cursor: pointer;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.chat-interface {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 1rem;
}

.messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.message {
  max-width: 70%;
  padding: 0.75rem 1rem;
  border-radius: 12px;
}

.message.user {
  background: #007bff;
  color: white;
  align-self: flex-end;
}

.message.assistant {
  background: white;
  align-self: flex-start;
  border: 1px solid #ddd;
}

.input-area {
  display: flex;
  gap: 0.5rem;
  padding: 1rem 0;
}

.input-area input[type="text"] {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.input-area button {
  padding: 0.75rem 1.5rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.data-table, .plan-review {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  margin: 0.5rem 0;
}

.data-table table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th, .data-table td {
  padding: 0.5rem;
  border: 1px solid #ddd;
  text-align: left;
}

.data-table input {
  width: 100%;
  padding: 0.25rem;
  border: 1px solid #ccc;
}

.plan-review ol {
  margin: 1rem 0;
  padding-left: 1.5rem;
}

.plan-review .actions {
  display: flex;
  gap: 0.5rem;
}
```

---

## Phase 6: Run & Test

### 6.1 Start backend

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6.2 Start frontend

```bash
cd frontend
npm install
npm run dev
```

### 6.3 Test flow

1. Open frontend at `http://localhost:5173`
2. Create new chat
3. Send message: "Add hemoglobin 14.5 for Juan Perez"
4. Or attach image of handwritten results
5. Review extracted data in editable table
6. Review execution plan
7. Click Execute to run actions

---

## Phase 7: Enhancements (Optional)

### 7.1 Audio recording in frontend

```tsx
const [isRecording, setIsRecording] = useState(false)
const mediaRecorder = useRef<MediaRecorder | null>(null)

const startRecording = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  mediaRecorder.current = new MediaRecorder(stream)
  const chunks: Blob[] = []
  
  mediaRecorder.current.ondataavailable = e => chunks.push(e.data)
  mediaRecorder.current.onstop = () => {
    const blob = new Blob(chunks, { type: 'audio/webm' })
    const file = new File([blob], 'recording.webm', { type: 'audio/webm' })
    setFiles(prev => [...prev, file])
  }
  
  mediaRecorder.current.start()
  setIsRecording(true)
}

const stopRecording = () => {
  mediaRecorder.current?.stop()
  setIsRecording(false)
}
```

### 7.2 WebSocket for live browser view

```python
# backend/main.py
@app.websocket("/ws/browser")
async def browser_ws(websocket: WebSocket):
    await websocket.accept()
    while True:
        state = await browser.get_state()
        await websocket.send_json(state)
        await asyncio.sleep(1)
```

### 7.3 Exam inventory file

Create `backend/exam_inventory.json`:
```json
{
  "exams": {
    "hemograma": {
      "fields": ["hemoglobina", "hematocrito", "leucocitos", "plaquetas"],
      "units": {"hemoglobina": "g/dL", "hematocrito": "%"}
    },
    "quimica_sanguinea": {
      "fields": ["glucosa", "creatinina", "urea"],
      "units": {"glucosa": "mg/dL"}
    }
  }
}
```

Add to Gemini context for better interpretation of handwritten text.

---

## Summary

| Phase | Deliverable |
|-------|-------------|
| 1 | Project structure, dependencies |
| 2 | BrowserManager class (DOM extraction + actions) |
| 3 | GeminiAgent class (single AI, full context) |
| 4 | FastAPI backend (endpoints + database) |
| 5 | React frontend (chat + data review + plan) |
| 6 | Run & test |
| 7 | Optional: audio, websocket, inventory |

Each phase is self-contained. Test after each phase before moving to the next.
