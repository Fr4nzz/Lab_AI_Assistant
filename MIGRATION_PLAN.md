# Migration Plan: Lobechat → Vercel AI Chatbot

## Overview

Migrate from Lobechat Docker container to Vercel AI Chatbot for full frontend customization while keeping the existing Python FastAPI + LangGraph backend. Self-hosted on Windows PC.

## Architecture Decision

**Chosen Approach: Option A - Frontend Replacement**

Keep the Python backend (FastAPI + LangGraph + Playwright) and replace only the Lobechat UI with Vercel AI Chatbot.

```
┌─────────────────────────────────────────────┐
│  Vercel AI Chatbot (Next.js 14)             │
│  ┌─────────────────────────────────────┐    │
│  │  Custom Lab Components               │    │
│  │  - BrowserTabsPanel (view + edit)    │    │
│  │  - Tool Settings (enable/disable)    │    │
│  │  - Voice Recording Button            │    │
│  │  - Model Selector                    │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │  Chat Interface (shadcn/ui)          │    │
│  │  - Message streaming                 │    │
│  │  - File attachments                  │    │
│  │  - Audio attachments                 │    │
│  └─────────────────────────────────────┘    │
└──────────────────┬──────────────────────────┘
                   │ HTTP/SSE
                   ↓
┌─────────────────────────────────────────────┐
│  FastAPI Backend (existing)                 │
│  - /v1/chat/completions (main chat)         │
│  - /api/chat/audio (native audio support)   │
│  - /api/browser/tabs                        │
│  - /api/tools/execute (manual tool calls)   │
│  - LangGraph + 8 tools                      │
│  - Playwright browser automation            │
└─────────────────────────────────────────────┘
```

**No Docker required!** Run Next.js directly on Windows with `npm run dev`.

---

## Migration Phases

---

### Phase 1: Project Setup

#### 1.1 Clone Vercel AI Chatbot (Recommended)

```bash
# Clone the template (recommended - can pull updates later)
git clone https://github.com/vercel/ai-chatbot.git frontend-new
cd frontend-new

# Change remote to your own repo
git remote rename origin upstream
git remote add origin https://github.com/yourusername/your-repo.git

# Install dependencies
npm install
```

**Why clone instead of create-next-app:**
- Can `git pull upstream main` to get Vercel's updates
- Keeps full git history for reference
- Just change the remote to push to your own repo

#### 1.2 Remove Vercel-specific Dependencies (Required for Self-Hosting)

```bash
# Remove Vercel-only packages
npm uninstall @vercel/blob @vercel/analytics @neondatabase/serverless

# Install local alternatives
npm install better-sqlite3  # For local SQLite database
```

**Keep these packages** (they work without Vercel):
- `ai` - Vercel AI SDK core (works anywhere)
- `@ai-sdk/openai` - OpenAI-compatible provider
- `@ai-sdk/google` - Google GenAI provider (for native audio)

#### 1.3 Configure Environment Variables

Create `.env.local`:

```env
# Backend connection
BACKEND_URL=http://localhost:8000

# Database (local SQLite)
DATABASE_URL=file:./chat.db

# OpenRouter for topic generation (free model)
OPENROUTER_API_KEY=sk-or-...

# Auth (disabled initially)
AUTH_DISABLED=true
```

#### 1.4 Run Development Server

```bash
# No Docker needed! Just run directly on Windows
npm run dev

# Opens at http://localhost:3000
```

---

### Phase 2: Backend Integration

#### 2.1 Create Chat API Route (Proxy to Python Backend)

Create `app/api/chat/route.ts`:

```typescript
export async function POST(request: Request) {
  const body = await request.json();
  const { messages, model, enabledTools } = body;

  // Forward to Python backend with tool settings
  const response = await fetch(`${process.env.BACKEND_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: model || 'lab-assistant',
      messages,
      stream: true,
      // Pass enabled tools to backend
      tools: enabledTools,
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

#### 2.2 Create Audio Chat Endpoint (Native Audio Support)

Since OpenAI-compatible API doesn't support native audio, create a separate endpoint that uses Google GenAI directly.

Create `app/api/chat/audio/route.ts`:

```typescript
export async function POST(request: Request) {
  const formData = await request.formData();
  const audio = formData.get('audio') as Blob;
  const messages = JSON.parse(formData.get('messages') as string);
  const enabledTools = JSON.parse(formData.get('enabledTools') as string);

  // Forward to Python backend's native audio endpoint
  const backendFormData = new FormData();
  backendFormData.append('audio', audio);
  backendFormData.append('messages', JSON.stringify(messages));
  backendFormData.append('enabled_tools', JSON.stringify(enabledTools));

  const response = await fetch(`${process.env.BACKEND_URL}/api/chat/audio`, {
    method: 'POST',
    body: backendFormData,
  });

  return new Response(response.body, {
    headers: {
      'Content-Type': 'text/event-stream',
    },
  });
}
```

**Backend changes needed:** Add `/api/chat/audio` endpoint to `server.py` that sends audio natively to Gemini (your backend already supports multimodal via `langchain-google-genai`).

#### 2.3 Create Browser Tabs Endpoint

Create `app/api/browser/tabs/route.ts`:

```typescript
export async function GET() {
  const res = await fetch(`${process.env.BACKEND_URL}/api/browser/tabs`);
  return Response.json(await res.json());
}
```

#### 2.4 Create Manual Tool Execution Endpoint

For when users manually edit fields in the UI and want to apply changes.

Create `app/api/tools/execute/route.ts`:

```typescript
export async function POST(request: Request) {
  const { tool, args } = await request.json();

  // Forward to Python backend tool executor
  const response = await fetch(`${process.env.BACKEND_URL}/api/tools/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool, args }),
  });

  return Response.json(await response.json());
}
```

**Backend changes needed:** Add `/api/tools/execute` endpoint that executes a single tool directly.

#### 2.5 Topic Generation with OpenRouter Free Model

Create `lib/generate-title.ts`:

```typescript
import { generateText } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';

const openrouter = createOpenAI({
  baseURL: 'https://openrouter.ai/api/v1',
  apiKey: process.env.OPENROUTER_API_KEY,
});

export async function generateChatTitle(firstMessage: string): Promise<string> {
  const { text } = await generateText({
    model: openrouter('google/gemini-2.0-flash-exp:free'),
    prompt: `Generate a very short title (3-5 words, in Spanish) for a conversation that starts with: "${firstMessage}"`,
    maxTokens: 20,
  });

  return text.trim();
}
```

---

### Phase 3: Model Configuration

#### 3.1 Custom Model List

Create `lib/models.ts`:

```typescript
export interface ModelConfig {
  id: string;
  name: string;
  provider: 'custom' | 'openrouter';
  description?: string;
}

export const availableModels: ModelConfig[] = [
  {
    id: 'lab-assistant',
    name: 'Lab Assistant (Gemini)',
    provider: 'custom',
    description: 'Default model with API key rotation',
  },
  {
    id: 'google/gemini-2.0-flash-exp:free',
    name: 'Gemini 2.0 Flash (Free)',
    provider: 'openrouter',
    description: 'OpenRouter free tier',
  },
  // Future: Add paid OpenRouter models
  // {
  //   id: 'google/gemini-pro',
  //   name: 'Gemini Pro (Paid)',
  //   provider: 'openrouter',
  // },
];

export const defaultModel = 'lab-assistant';
```

#### 3.2 Model Selector Component

Create `components/model-selector.tsx`:

```typescript
'use client';

import { availableModels, ModelConfig } from '@/lib/models';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface ModelSelectorProps {
  value: string;
  onChange: (model: string) => void;
}

export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-[200px]">
        <SelectValue placeholder="Select model" />
      </SelectTrigger>
      <SelectContent>
        {availableModels.map((model) => (
          <SelectItem key={model.id} value={model.id}>
            {model.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

---

### Phase 4: Tool Settings

#### 4.1 Tool Configuration

Create `lib/tools.ts`:

```typescript
export interface ToolConfig {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
}

export const defaultTools: ToolConfig[] = [
  { id: 'search_orders', name: 'Buscar Órdenes', description: 'Search orders by patient', enabled: true },
  { id: 'get_order_results', name: 'Ver Resultados', description: 'Open order results', enabled: true },
  { id: 'get_order_info', name: 'Info de Orden', description: 'Get order details', enabled: true },
  { id: 'edit_results', name: 'Editar Resultados', description: 'Fill result fields', enabled: true },
  { id: 'edit_order_exams', name: 'Editar Exámenes', description: 'Add/remove exams', enabled: true },
  { id: 'create_new_order', name: 'Nueva Orden', description: 'Create new order', enabled: true },
  { id: 'get_available_exams', name: 'Lista de Exámenes', description: 'Get exam list', enabled: true },
  { id: 'ask_user', name: 'Preguntar Usuario', description: 'Ask for clarification', enabled: true },
];
```

#### 4.2 Tool Settings Component

Create `components/tool-settings.tsx`:

```typescript
'use client';

import { ToolConfig } from '@/lib/tools';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ToolSettingsProps {
  tools: ToolConfig[];
  onToggle: (toolId: string, enabled: boolean) => void;
}

export function ToolSettings({ tools, onToggle }: ToolSettingsProps) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon">
          <Settings className="h-4 w-4" />
        </Button>
      </SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Herramientas del AI</SheetTitle>
        </SheetHeader>
        <div className="mt-4 space-y-4">
          {tools.map((tool) => (
            <div key={tool.id} className="flex items-center justify-between">
              <div>
                <Label htmlFor={tool.id}>{tool.name}</Label>
                <p className="text-sm text-muted-foreground">{tool.description}</p>
              </div>
              <Switch
                id={tool.id}
                checked={tool.enabled}
                onCheckedChange={(checked) => onToggle(tool.id, checked)}
              />
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}
```

---

### Phase 5: Custom UI Components (After Integration Works)

These components will be planned in detail after basic chat integration is working.

#### 5.1 BrowserTabsPanel with Manual Editing

**Purpose:** View opened browser tabs, see field values, manually edit and send changes.

**Features:**
- List all open browser tabs (orders, results pages)
- Click a tab to see its fields and current values
- Highlight AI-modified fields (different color)
- Edit fields manually in a form
- "Enviar Cambios" button → calls `/api/tools/execute` with `edit_results`
- Add/remove exams from orders → calls `edit_order_exams`

```typescript
// Rough structure - to be designed after Phase 2 works
interface BrowserTabsPanelProps {
  // Will fetch from /api/browser/tabs
}

// Tab types:
// - reportes2: Show exam fields with values, allow editing
// - ordenes/edit: Show order info, allow adding/removing exams
// - ordenes/create: Show new order form, allow editing exams
```

#### 5.2 Voice Recording Button

**Purpose:** Record audio and send to AI as native audio (not transcription).

**Features:**
- Microphone button in chat input area
- Records audio using Web Audio API
- Sends to `/api/chat/audio` endpoint
- Backend sends audio natively to Gemini

```typescript
// Uses MediaRecorder API
// Sends audio blob to backend
// Backend uses langchain-google-genai for native audio processing
```

---

### Phase 6: Chat History

#### 6.1 Use Vercel AI Chatbot's Built-in Database

Use the built-in Drizzle ORM schema, but with local SQLite instead of Neon Postgres.

```typescript
// drizzle.config.ts - modify for SQLite
export default {
  schema: './lib/db/schema.ts',
  driver: 'better-sqlite3',
  dbCredentials: {
    url: './chat.db',
  },
};
```

#### 6.2 Start Fresh (No Migration)

No need to migrate existing Lobechat data. Start with empty database.

---

### Phase 7: Authentication

#### 7.1 Disable Initially

Modify `middleware.ts` to allow all routes:

```typescript
import { NextResponse } from 'next/server';

export function middleware() {
  // Auth disabled for local development
  return NextResponse.next();
}

export const config = {
  matcher: [], // Don't match any routes
};
```

#### 7.2 Add Auth Later (Optional)

Enable Auth.js when needed for multi-user support.

---

## Backend Changes Required

### New Endpoints to Add to `server.py`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat/audio` | POST | Accept native audio, send to Gemini directly |
| `/api/tools/execute` | POST | Execute a single tool by name with args |
| `/api/tools/list` | GET | Return list of available tools (for settings) |

### Modify Existing:

| Endpoint | Change |
|----------|--------|
| `/v1/chat/completions` | Accept `tools` param to filter enabled tools |

---

## Migration Checklist

### Phase 1: Setup
- [ ] Clone Vercel AI Chatbot repository
- [ ] Remove Vercel-specific dependencies (`@vercel/blob`, `@vercel/analytics`, `@neondatabase/serverless`)
- [ ] Install `better-sqlite3` for local database
- [ ] Configure `.env.local` with backend URL
- [ ] Run `npm run dev` - verify Next.js starts

### Phase 2: Backend Integration
- [ ] Create `/api/chat/route.ts` - proxy to Python backend
- [ ] Test chat streaming works with existing backend
- [ ] Create `/api/browser/tabs/route.ts`
- [ ] Create `/api/tools/execute/route.ts`
- [ ] Add topic generation with OpenRouter free model
- [ ] **Backend:** Add `/api/chat/audio` endpoint for native audio
- [ ] **Backend:** Add `/api/tools/execute` endpoint
- [ ] **Backend:** Modify chat endpoint to accept `tools` filter

### Phase 3: Model Configuration
- [ ] Create model list configuration
- [ ] Add model selector component to UI
- [ ] Test switching between models

### Phase 4: Tool Settings
- [ ] Create tool configuration
- [ ] Add tool settings panel to UI
- [ ] Pass enabled tools to backend
- [ ] Test tool filtering works

### Phase 5: Custom UI (After Integration Works)
- [ ] Design BrowserTabsPanel component
- [ ] Implement field viewing for open tabs
- [ ] Implement manual field editing
- [ ] Add "Enviar Cambios" functionality
- [ ] Design voice recording button
- [ ] Implement audio recording
- [ ] Test native audio with Gemini

### Phase 6: Database
- [ ] Configure Drizzle with SQLite
- [ ] Run migrations
- [ ] Test chat history saving/loading

### Phase 7: Polish
- [ ] Disable auth in middleware
- [ ] Style UI (Tailwind)
- [ ] Error handling
- [ ] Loading states

---

## Running the App

### Development (No Docker!)

Terminal 1 - Python Backend:
```bash
cd backend
python server.py
# Runs on http://localhost:8000
```

Terminal 2 - Next.js Frontend:
```bash
cd frontend-new
npm run dev
# Runs on http://localhost:3000
```

### Production (Optional Docker)

Only if you want containerized deployment later:
```bash
docker-compose up
```

But for development on your Windows PC, **just run both servers directly**.

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| SSE streaming compatibility | High | Test early in Phase 2 |
| Native audio API differences | Medium | Keep OpenAI-compat for text, separate endpoint for audio |
| Database migration | Low | Start fresh, no migration needed |
| Learning curve (Next.js) | Low | Well-documented |

---

## Resources

- [Vercel AI Chatbot Repo](https://github.com/vercel/ai-chatbot)
- [Vercel AI SDK Docs](https://sdk.vercel.ai/docs)
- [shadcn/ui Components](https://ui.shadcn.com)
- [Next.js App Router](https://nextjs.org/docs/app)
- [Drizzle ORM with SQLite](https://orm.drizzle.team/docs/get-started-sqlite)
