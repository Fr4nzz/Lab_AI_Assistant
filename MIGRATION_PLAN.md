# Migration Plan: Lobechat → Vercel AI Chatbot

## Overview

Migrate from Lobechat Docker container to Vercel AI Chatbot for full frontend customization while keeping the existing Python FastAPI + LangGraph backend.

## Architecture Decision

**Chosen Approach: Option A - Frontend Replacement**

Keep the Python backend (FastAPI + LangGraph + Playwright) and replace only the Lobechat UI with Vercel AI Chatbot.

```
┌─────────────────────────────────────────────┐
│  Vercel AI Chatbot (Next.js 14)             │
│  ┌─────────────────────────────────────┐    │
│  │  Custom Lab Components               │    │
│  │  - OrdersTable                       │    │
│  │  - ExamResultsForm                   │    │
│  │  - BrowserTabsPanel                  │    │
│  │  - PatientSearch                     │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │  Chat Interface (shadcn/ui)          │    │
│  │  - Message streaming                 │    │
│  │  - Tool call visualization           │    │
│  │  - File attachments                  │    │
│  └─────────────────────────────────────┘    │
└──────────────────┬──────────────────────────┘
                   │ HTTP/SSE (OpenAI-compatible)
                   ↓
┌─────────────────────────────────────────────┐
│  FastAPI Backend (existing)                 │
│  - /v1/chat/completions (OpenAI-compat)     │
│  - /api/browser/screenshot                  │
│  - /api/browser/tabs                        │
│  - LangGraph + 8 tools                      │
│  - Playwright browser automation            │
└─────────────────────────────────────────────┘
```

## Migration Phases

---

### Phase 1: Project Setup

#### 1.1 Clone and Configure Vercel AI Chatbot

```bash
# Clone the template
git clone https://github.com/vercel/ai-chatbot.git frontend-new

# Or use create-next-app
npx create-next-app@latest frontend-new --example https://github.com/vercel/ai-chatbot
```

#### 1.2 Remove Vercel-specific Dependencies (Optional)

If self-hosting, remove:
- `@vercel/blob` (file storage)
- `@neondatabase/serverless` (replace with local PostgreSQL or SQLite)
- `@vercel/analytics`

#### 1.3 Configure Environment Variables

```env
# .env.local
# Backend connection
BACKEND_URL=http://localhost:8000

# Auth (optional - can disable initially)
AUTH_SECRET=your-secret-here

# Database (can use existing SQLite or new PostgreSQL)
DATABASE_URL=postgres://... or sqlite:///./lab_assistant.db
```

---

### Phase 2: Backend API Adapter

#### 2.1 Create API Route to Proxy to Python Backend

Create `app/api/chat/route.ts`:

```typescript
import { createOpenAICompatibleStream } from '@/lib/backend-adapter';

export async function POST(request: Request) {
  const body = await request.json();

  // Forward to Python backend
  const response = await fetch(`${process.env.BACKEND_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer dummy', // Your backend accepts any key
    },
    body: JSON.stringify({
      model: 'lab-assistant',
      messages: body.messages,
      stream: true,
    }),
  });

  // Stream the response back
  return new Response(response.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
```

#### 2.2 Add Browser State Endpoints

Create `app/api/browser/route.ts`:

```typescript
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const action = searchParams.get('action');

  if (action === 'screenshot') {
    const res = await fetch(`${process.env.BACKEND_URL}/api/browser/screenshot`);
    return Response.json(await res.json());
  }

  if (action === 'tabs') {
    const res = await fetch(`${process.env.BACKEND_URL}/api/browser/tabs`);
    return Response.json(await res.json());
  }

  return Response.json({ error: 'Unknown action' }, { status: 400 });
}
```

---

### Phase 3: Custom UI Components

#### 3.1 Lab-Specific Components to Build

| Component | Purpose | Priority |
|-----------|---------|----------|
| `BrowserTabsPanel` | Show open browser tabs with patient info | High |
| `OrdersTable` | Display recent orders with search | High |
| `ExamResultsViewer` | Show/edit exam results in structured format | High |
| `ScreenshotPreview` | Live browser screenshot | Medium |
| `ToolCallCard` | Visualize tool executions (search, edit, etc.) | Medium |
| `PatientSearchInput` | Autocomplete patient search | Medium |
| `ExamSelector` | Multi-select exam codes for new orders | Low |

#### 3.2 Example: BrowserTabsPanel Component

```typescript
// components/browser-tabs-panel.tsx
'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface BrowserTab {
  id: string;
  type: string;
  patient?: string;
  orderId?: number;
}

export function BrowserTabsPanel() {
  const [tabs, setTabs] = useState<BrowserTab[]>([]);

  useEffect(() => {
    const fetchTabs = async () => {
      const res = await fetch('/api/browser?action=tabs');
      const data = await res.json();
      setTabs(data.tabs || []);
    };

    fetchTabs();
    const interval = setInterval(fetchTabs, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Browser Tabs</CardTitle>
      </CardHeader>
      <CardContent>
        {tabs.map((tab) => (
          <div key={tab.id} className="flex items-center gap-2 py-1">
            <Badge variant={tab.type === 'reportes2' ? 'default' : 'secondary'}>
              {tab.type}
            </Badge>
            <span>{tab.patient || `Order #${tab.orderId}`}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
```

#### 3.3 Modify Chat Interface for Tool Visualization

Extend the default message rendering to show tool calls:

```typescript
// components/message.tsx (extend existing)
function ToolCallDisplay({ toolCall }: { toolCall: ToolCall }) {
  const icons: Record<string, string> = {
    search_orders: '🔍',
    get_order_results: '📋',
    edit_results: '✏️',
    create_new_order: '➕',
  };

  return (
    <div className="flex items-center gap-2 p-2 bg-muted rounded-md">
      <span>{icons[toolCall.name] || '🔧'}</span>
      <span className="font-medium">{toolCall.name}</span>
      <code className="text-xs">{JSON.stringify(toolCall.args)}</code>
    </div>
  );
}
```

---

### Phase 4: Chat History Integration

#### Option A: Use Existing Python Database

Modify Next.js to read from the existing SQLite database:

```typescript
// lib/db.ts
import Database from 'better-sqlite3';

const db = new Database('../backend/lab_assistant.db');

export async function getChats(userId: string) {
  return db.prepare('SELECT * FROM chats ORDER BY updated_at DESC').all();
}

export async function getMessages(chatId: string) {
  return db.prepare('SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at').all(chatId);
}
```

#### Option B: Migrate to Drizzle ORM

Use Vercel AI Chatbot's built-in Drizzle schema and migrate existing data.

---

### Phase 5: Authentication (Optional)

#### 5.1 Simple Approach: Disable Auth Initially

```typescript
// Remove auth checks for local/internal use
// middleware.ts - allow all routes
export function middleware() {
  return NextResponse.next();
}
```

#### 5.2 Later: Add Auth.js

Use existing Auth.js configuration from Vercel AI Chatbot for multi-user support.

---

### Phase 6: Docker Integration

#### 6.1 Update docker-compose.yml

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./browser_data:/app/browser_data
      - ./backend/data:/app/data
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}

  frontend:
    build: ./frontend-new
    ports:
      - "3000:3000"
    environment:
      - BACKEND_URL=http://backend:8000
    depends_on:
      - backend

  # Remove lobechat service
```

#### 6.2 Dockerfile for Next.js Frontend

```dockerfile
# frontend-new/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
```

---

### Phase 7: Advanced Features (Future)

#### 7.1 Real-time Browser Preview

```typescript
// WebSocket connection to stream browser screenshots
// Could use Server-Sent Events or WebSocket
```

#### 7.2 Structured Data Entry

```typescript
// Custom forms for exam results instead of chat-based entry
// Direct table editing with validation
```

#### 7.3 Voice Input

```typescript
// Integrate Web Speech API for voice commands
// "Buscar paciente Juan Pérez"
```

---

## Migration Checklist

### Pre-Migration
- [ ] Backup existing database and browser_data
- [ ] Document current Lobechat customizations (if any)
- [ ] Test Python backend independently

### Phase 1: Setup
- [ ] Clone Vercel AI Chatbot
- [ ] Remove unnecessary Vercel dependencies
- [ ] Configure environment variables
- [ ] Test basic Next.js app runs

### Phase 2: Backend Connection
- [ ] Create API proxy route
- [ ] Test chat streaming works
- [ ] Add browser endpoint proxies
- [ ] Verify tool calls display correctly

### Phase 3: Custom Components
- [ ] Build BrowserTabsPanel
- [ ] Build OrdersTable
- [ ] Build ToolCallCard
- [ ] Integrate into chat layout

### Phase 4: Data Migration
- [ ] Choose database strategy
- [ ] Migrate or connect existing chat history
- [ ] Test history loading/saving

### Phase 5: Polish
- [ ] Style with Tailwind (match lab branding)
- [ ] Add error handling
- [ ] Mobile responsive design
- [ ] Loading states

### Phase 6: Deploy
- [ ] Update docker-compose.yml
- [ ] Test full stack in Docker
- [ ] Remove old Lobechat container
- [ ] Document new setup

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| SSE streaming compatibility | High | Test early, fallback to polling |
| Auth complexity | Medium | Start without auth, add later |
| Database migration | Medium | Keep both options, migrate gradually |
| Learning curve (Next.js) | Low | Well-documented, lots of examples |
| Docker networking | Low | Use docker-compose networks |

---

## Estimated Effort

| Phase | Effort | Notes |
|-------|--------|-------|
| Phase 1: Setup | 2-4 hours | Straightforward cloning |
| Phase 2: API Adapter | 4-8 hours | Main integration work |
| Phase 3: Custom UI | 8-16 hours | Depends on requirements |
| Phase 4: History | 2-4 hours | Database decisions |
| Phase 5: Auth | 2-4 hours | Optional |
| Phase 6: Docker | 2-4 hours | Configuration |

**Total: 20-40 hours** for a functional migration

---

## Next Steps

1. Clone Vercel AI Chatbot repository
2. Set up local development environment
3. Create the API proxy route to Python backend
4. Test basic chat functionality
5. Iterate on custom components

---

## Resources

- [Vercel AI Chatbot Repo](https://github.com/vercel/ai-chatbot)
- [Vercel AI SDK Docs](https://sdk.vercel.ai/docs)
- [shadcn/ui Components](https://ui.shadcn.com)
- [Next.js App Router](https://nextjs.org/docs/app)
