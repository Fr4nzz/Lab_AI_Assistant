# Telegram Bot Integration - Investigation & Fix Plan

## Status: IMPLEMENTED

The fix has been implemented. The Telegram bot now uses the Frontend HTTP API instead of direct SQLite access.

---

## Issue Summary

When sending an image to the Telegram bot, it fails with:
```
telegram_bot.services.backend - ERROR - Failed to create chat: no such table: chats
```

The root cause is that the Telegram bot tries to **directly access the SQLite database** instead of using the Frontend's HTTP API.

---

## Architecture Investigation

### Current Architecture (BROKEN)

```
┌─────────────────────┐
│  Telegram Bot       │
│  (telegram_bot/)    │
└─────────┬───────────┘
          │
          ├──── WRONG: Direct SQLite access ────────┐
          │     (file doesn't exist or wrong path)  │
          │                                         ▼
          │                           ┌─────────────────────────┐
          │                           │  SQLite Database        │
          │                           │  data/lab-assistant.db  │
          │                           │  (created by Frontend)  │
          │                           └─────────────────────────┘
          │
          └──── OK: HTTP API to Backend ────────────┐
                                                    ▼
                                      ┌─────────────────────────┐
                                      │  Backend (FastAPI)      │
                                      │  Port 8000              │
                                      │  /api/v1/chat/...       │
                                      └─────────────────────────┘
```

### Correct Architecture (IMPLEMENTED)

```
┌─────────────────────┐
│  Telegram Bot       │
│  (telegram_bot/)    │
└─────────┬───────────┘
          │
          └──── HTTP API to Frontend ───────────────┐
                                                    ▼
                                      ┌─────────────────────────┐
                                      │  Frontend (Nuxt)        │
                                      │  Port 3000              │
                                      │  /api/chats             │
                                      │  /api/chats/[id]        │
                                      └───────────┬─────────────┘
                                                  │
                              ┌────────────────────┴────────────────────┐
                              │                                         │
                              ▼                                         ▼
                ┌─────────────────────────┐           ┌─────────────────────────┐
                │  SQLite Database        │           │  Backend (FastAPI)      │
                │  data/lab-assistant.db  │           │  /api/chat/aisdk        │
                └─────────────────────────┘           └─────────────────────────┘
```

---

## Codebase Findings

### 1. Frontend Database Management

**Location:** `frontend-nuxt/server/utils/db.ts`

```typescript
// Database singleton - creates tables on first access
export function useDB() {
  if (!_db) {
    const dbPath = getDbPath()  // ./data/lab-assistant.db
    const absolutePath = resolve(process.cwd(), dbPath)

    const sqlite = new Database(absolutePath)
    sqlite.pragma('journal_mode = WAL')

    _db = drizzle(sqlite, { schema })
    initializeDatabase(sqlite)  // Creates tables if not exist
  }
  return _db
}
```

**Key Point:** Database is created ONLY when the Frontend starts and handles its first request.

### 2. Frontend Chat API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chats` | GET | List all chats |
| `/api/chats` | POST | Create new chat |
| `/api/chats/[id]` | GET | Get chat with messages |
| `/api/chats/[id]` | POST | Send message, stream response |
| `/api/chats/[id]` | DELETE | Delete chat |
| `/api/chats/[id]/title` | PATCH | Update chat title |

**Chat Creation (POST /api/chats):**
```typescript
// frontend-nuxt/server/api/chats.post.ts
export default defineEventHandler(async (event) => {
  await getUserSession(event)  // Auth check

  const body = await readValidatedBody(event, ...)

  const chat = await createChat({
    id: body.id,
    title: body.title || 'Nuevo Chat'
  })

  return chat
})
```

**Message Sending (POST /api/chats/[id]):**
```typescript
// frontend-nuxt/server/api/chats/[id].post.ts
export default defineEventHandler(async (event) => {
  // 1. Save user message to DB
  await addMessage({ chatId, role: 'user', content, parts })

  // 2. Forward to backend for AI processing
  const response = await fetch(`${BACKEND_URL}/api/chat/aisdk`, {
    method: 'POST',
    body: JSON.stringify({ messages, ... }),
    headers: { 'x-thread-id': chatId }
  })

  // 3. Stream response and save assistant message
  // ... streaming logic ...

  await addMessage({ chatId, role: 'assistant', content, parts })
})
```

### 3. Backend API

**Location:** `backend/server.py`

The backend has NO database - it's stateless. Key endpoints:

- `POST /api/chat/aisdk` - AI SDK streaming protocol
- `POST /api/v1/chat/completions` - OpenAI-compatible endpoint

Both endpoints:
- Receive messages array in request body
- Use `x-thread-id` header for conversation tracking
- Stream responses using SSE

### 4. Current Telegram Bot Issue

**Location:** `telegram_bot/services/backend.py`

```python
# PROBLEM: Direct database access
DB_PATH = Path(__file__).parent.parent.parent / "data" / "lab-assistant.db"

def get_recent_chats(self, limit: int = 3):
    # WRONG: Direct sqlite3 connection
    conn = sqlite3.connect(str(DB_PATH))  # File doesn't exist!
    cursor = conn.execute("SELECT id, title FROM chats...")

def create_chat(self, title: str):
    # WRONG: Direct insert
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("INSERT INTO chats...")
```

---

## Research Findings

### Vercel AI SDK Data Stream Protocol

**Source:** [AI SDK Stream Protocol](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol)

The backend uses AI SDK Data Stream Protocol v1 with SSE format:
```
data: {"type":"text-delta","delta":"Hello"}
data: {"type":"tool-input-start","toolCallId":"...","toolName":"..."}
data: {"type":"tool-input-available","toolCallId":"...","input":{...}}
data: [DONE]
```

### Python SSE Streaming

**Source:** [httpx-sse](https://github.com/florimondmanca/httpx-sse)

For consuming SSE streams in Python:
```python
from httpx_sse import aconnect_sse

async with httpx.AsyncClient() as client:
    async with aconnect_sse(client, "POST", url, json=data) as event_source:
        async for sse in event_source.aiter_sse():
            print(sse.event, sse.data)
```

---

## Fix Plan

### Step 1: Update Backend Service to Use Frontend API

Replace direct database access with HTTP calls to Frontend:

```python
# NEW: Use Frontend API
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

class BackendService:
    async def get_recent_chats(self, limit: int = 3):
        """Get recent chats via Frontend API."""
        async with self.client.get(f"{FRONTEND_URL}/api/chats") as response:
            chats = response.json()
            return [(c["id"], c["title"]) for c in chats[:limit]]

    async def create_chat(self, title: str):
        """Create chat via Frontend API."""
        async with self.client.post(
            f"{FRONTEND_URL}/api/chats",
            json={"title": title}
        ) as response:
            chat = response.json()
            return chat["id"]
```

### Step 2: Use Frontend's Message Endpoint for AI

Instead of calling backend directly, use Frontend's `/api/chats/[id]` which:
1. Saves user message to database
2. Forwards to backend for AI processing
3. Saves assistant response to database
4. Streams everything properly

```python
async def send_message(self, chat_id: str, message: str, images: List[bytes]):
    """Send message via Frontend API (handles DB + backend)."""
    content = self._build_content(message, images)

    async with aconnect_sse(
        self.client,
        "POST",
        f"{FRONTEND_URL}/api/chats/{chat_id}",
        json={"messages": [{"role": "user", "content": content}]}
    ) as event_source:
        async for sse in event_source.aiter_sse():
            # Parse AI SDK protocol events
            yield self._parse_event(sse.data)
```

### Step 3: Add httpx-sse Dependency

```
pip install httpx-sse
```

### Step 4: Update Handlers to Use Async Methods

Convert synchronous database calls to async HTTP calls.

---

## Files to Modify

1. **telegram_bot/services/backend.py** - Complete rewrite
   - Remove direct database access
   - Use Frontend HTTP API for all operations
   - Add proper SSE streaming support

2. **telegram_bot/requirements.txt** - Add httpx-sse

3. **telegram_bot/handlers/*.py** - Update to use async API methods

4. **.env.example** - Add FRONTEND_URL variable

---

## API Mapping

| Current (Direct DB) | New (Frontend API) |
|--------------------|-------------------|
| `sqlite3.connect()` | `httpx.AsyncClient()` |
| `SELECT FROM chats` | `GET /api/chats` |
| `INSERT INTO chats` | `POST /api/chats` |
| `UPDATE chats` | `PATCH /api/chats/[id]/title` |
| `POST /api/v1/chat/completions` | `POST /api/chats/[id]` |

---

## Testing Plan

1. Start Frontend: `npm run dev` in frontend-nuxt/
2. Start Backend: `python server.py` in backend/
3. Start Telegram Bot: `python -m telegram_bot.bot`
4. Send photo to bot
5. Verify:
   - Chat created via API (check frontend logs)
   - Message saved to database
   - AI response streamed back
   - Tool calls displayed
   - Chat URL works

---

## References

- [Vercel AI SDK Stream Protocol](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol)
- [httpx-sse GitHub](https://github.com/florimondmanca/httpx-sse)
- [py-ai-datastream](https://github.com/elementary-data/py-ai-datastream) - Python AI SDK implementation
