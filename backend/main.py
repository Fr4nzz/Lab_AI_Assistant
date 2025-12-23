"""FastAPI application for Lab Assistant."""
import asyncio
import base64
import sys
from typing import List, Optional
from contextlib import asynccontextmanager

# Fix for Windows asyncio + Playwright
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import settings
from gemini_handler import GeminiHandler
from browser_manager import BrowserManager
from database import Database
from lab_agent import LabAgent


# Global instances
db: Database = None
browser: BrowserManager = None
gemini: GeminiHandler = None
agent: LabAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db, browser, gemini, agent
    
    # Startup
    print("Starting Lab Assistant...")
    
    db = Database(settings.database_url)
    
    gemini = GeminiHandler(
        api_keys=settings.gemini_api_keys,
        model_name=settings.gemini_model
    )
    
    browser = BrowserManager(user_data_dir=settings.browser_data_dir)
    await browser.start(headless=False, browser=settings.browser_channel)
    
    # Navigate to target URL
    await browser.navigate(settings.target_url)
    
    agent = LabAgent(
        gemini_handler=gemini,
        browser_manager=browser,
        database=db
    )
    
    print(f"Lab Assistant ready! Browser at: {browser.page.url}")
    
    yield
    
    # Shutdown
    print("Shutting down Lab Assistant...")
    await browser.stop()


app = FastAPI(
    title="Lab Assistant API",
    description="AI-powered laboratory result entry assistant",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Pydantic Models ==============

class ChatCreate(BaseModel):
    title: Optional[str] = None


class PlanExecute(BaseModel):
    chat_id: str
    plan: dict


class MessageResponse(BaseModel):
    mode: str
    question: Optional[str] = None
    options: Optional[List[str]] = None
    understanding: Optional[str] = None
    extracted_data: Optional[List[dict]] = None
    steps: Optional[List[dict]] = None
    suggestions: Optional[List[dict]] = None
    error: Optional[str] = None


# ============== API Endpoints ==============

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "browser_url": browser.page.url if browser and browser.page else None
    }


@app.get("/api/chats")
async def list_chats():
    """List all chat sessions."""
    return db.get_chats()


@app.post("/api/chats")
async def create_chat(chat: ChatCreate):
    """Create a new chat session."""
    return db.create_chat(chat.title)


@app.get("/api/chats/{chat_id}")
async def get_chat(chat_id: str):
    """Get a specific chat."""
    chat = db.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete a chat."""
    if db.delete_chat(chat_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Chat not found")


@app.get("/api/chats/{chat_id}/history")
async def get_chat_history(chat_id: str):
    """Get message history for a chat."""
    return db.get_messages(chat_id)


@app.post("/api/chat")
async def send_message(
    chat_id: str = Form(...),
    message: str = Form(""),
    files: List[UploadFile] = File(default=[])
):
    """
    Send a message to the AI agent.
    
    Accepts text message and optional file attachments (images/audio).
    """
    # Verify chat exists
    chat = db.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Process attachments
    attachments = []
    for file in files:
        content = await file.read()
        content_b64 = base64.b64encode(content).decode('utf-8')
        
        attachments.append({
            "type": file.content_type,
            "data": content_b64,
            "mime_type": file.content_type,
            "filename": file.filename
        })
    
    # Save user message
    attachment_refs = [{"filename": a["filename"], "type": a["type"]} for a in attachments] if attachments else None
    db.add_message(chat_id, "user", message, attachment_refs)
    
    # Process with agent
    try:
        response = await agent.process_message(
            chat_id=chat_id,
            message=message,
            attachments=attachments if attachments else None
        )
        return response
    except Exception as e:
        return {"mode": "error", "error": str(e)}


@app.post("/api/execute")
async def execute_plan(data: PlanExecute):
    """Execute an approved plan."""
    try:
        result = await agent.execute_plan(data.plan)
        
        # Update plan status in database
        pending_plan = db.get_pending_plan(data.chat_id)
        if pending_plan:
            status = "executed" if result["success"] else "failed"
            db.update_plan_status(pending_plan["id"], status)
        
        # Save assistant message
        db.add_message(data.chat_id, "assistant", result["message"])
        
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/browser/state")
async def get_browser_state():
    """Get current browser state."""
    try:
        state = await browser.get_state()
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/browser/screenshot")
async def get_screenshot():
    """Get current browser screenshot as base64."""
    try:
        screenshot = await browser.get_screenshot()
        return {"screenshot": screenshot}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/browser/navigate")
async def navigate_browser(url: str = Form(...)):
    """Navigate browser to a URL."""
    try:
        await browser.navigate(url)
        return {"success": True, "url": browser.page.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders")
async def get_orders_summary():
    """Get summary of recent orders."""
    try:
        return await agent.get_orders_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Run ==============

if __name__ == "__main__":
    import uvicorn
    # Note: --reload can cause issues on Windows with Playwright
    # Use reload=False for production, or run with: python main.py
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
