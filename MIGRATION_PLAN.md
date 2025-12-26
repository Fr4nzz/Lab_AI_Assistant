# Migration Plan: Lobechat → Custom Next.js + AI SDK

## Overview

Build a custom Next.js frontend using Vercel AI SDK to replace Lobechat. Self-hosted on Windows PC with full control over the UI.

**Approach: Build Fresh (Option B)** - Create a new Next.js app with AI SDK instead of modifying the Vercel AI Chatbot template.

---

## AI SDK Research Summary

### Available Providers

| Provider | Package | Best For |
|----------|---------|----------|
| **Google Generative AI** | `@ai-sdk/google` | Direct Gemini API, native audio, images |
| **OpenRouter** | `@openrouter/ai-sdk-provider` | Hundreds of models, free tier, fallbacks |
| **OpenAI Compatible** | `@ai-sdk/openai-compatible` | Custom backends (like your Python server) |
| **OpenAI** | `@ai-sdk/openai` | GPT models, Whisper transcription |
| **Anthropic** | `@ai-sdk/anthropic` | Claude models |

### Recommended Provider Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────┐  ┌──────────────────────────┐ │
│  │  @openrouter/ai-sdk-provider │  │     Python Backend       │ │
│  │                              │  │     (via fetch)          │ │
│  └──────────────┬───────────────┘  └────────────┬─────────────┘ │
│                 │                               │               │
│                 ▼                               ▼               │
│  ┌──────────────────────────────┐  ┌──────────────────────────┐ │
│  │ Topic Generation (FREE)      │  │ Main Chat + Tools        │ │
│  │ nvidia/nemotron-3-nano:free  │  │ + Audio + Browser        │ │
│  └──────────────────────────────┘  └──────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Why this approach:**
1. **Python Backend for main chat** - Handles key rotation, 8 lab tools, Playwright browser
2. **@openrouter/ai-sdk-provider for topic naming** - Uses FREE model `nvidia/nemotron-3-nano-30b-a3b:free` (same as Lobechat)
3. **Future: OpenRouter paid models** - Easy to add paid Gemini models when needed

---

## AI SDK Features We Will Use

### Core Features

| Feature | Support | Notes |
|---------|---------|-------|
| **useChat hook** | ✅ Full | Messages, streaming, status, callbacks |
| **Streaming** | ✅ Full | Real-time token streaming via SSE |
| **Tool Calling** | ✅ Full | Define tools, model calls them, show in UI |
| **File Attachments** | ✅ Experimental | Images, PDFs, text files via `experimental_attachments` |
| **Image Input** | ✅ Full | Send images to multimodal models |
| **Audio Transcription** | ✅ Full | `transcribe()` function for speech-to-text |
| **Native Audio Input** | ⚠️ Limited | Only Google & OpenAI audio models support file parts |

### useChat Hook Returns

```typescript
const {
  messages,        // Array of chat messages
  input,           // Current input value (controlled)
  setInput,        // Set input value
  handleInputChange, // Input change handler
  handleSubmit,    // Form submit handler (supports attachments)
  status,          // 'ready' | 'submitted' | 'streaming' | 'error'
  isLoading,       // Boolean loading state
  stop,            // Stop current stream
  reload,          // Retry last message
  error,           // Error object if failed
  setMessages,     // Manually set messages
} = useChat({
  api: '/api/chat',           // Custom endpoint
  headers: {},                // Custom headers
  body: {},                   // Extra body data
  onFinish: (message) => {},  // Called when response complete
  onError: (error) => {},     // Called on error
});
```

### File Attachments (Experimental)

```typescript
// Method 1: FileList from input
<input type="file" onChange={(e) => {
  handleSubmit(e, {
    experimental_attachments: e.target.files,
  });
}} />

// Method 2: Pre-built URLs
handleSubmit(e, {
  experimental_attachments: [
    { url: 'data:image/png;base64,...', contentType: 'image/png' },
    { url: 'https://example.com/file.pdf', contentType: 'application/pdf' },
  ],
});
```

### Audio Support Options

| Approach | How It Works | Provider |
|----------|--------------|----------|
| **Transcription** | `transcribe()` → text → chat | OpenAI Whisper, Groq, Deepgram |
| **Native Audio File** | Send audio as file part | Google Gemini, OpenAI gpt-4o-audio |
| **Your Backend** | Send audio to Python → Gemini native | Your FastAPI server |

**Recommendation:** Use your Python backend for native audio since it already uses `langchain-google-genai` which supports native audio.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Next.js Frontend (Port 3000)                  │
├─────────────────────────────────────────────────────────────────┤
│  Pages:                                                          │
│  ├── / (chat interface)                                         │
│  ├── /settings (model & tool settings)                          │
│  └── /api/...                                                   │
│                                                                  │
│  API Routes:                                                     │
│  ├── /api/chat          → Proxy to Python backend               │
│  ├── /api/chat/audio    → Native audio to Python backend        │
│  ├── /api/chat/title    → Generate title with @ai-sdk/google    │
│  ├── /api/browser/tabs  → Get browser tabs from Python          │
│  └── /api/tools/execute → Manual tool execution                 │
│                                                                  │
│  Components:                                                     │
│  ├── Chat (useChat hook)                                        │
│  ├── MessageList                                                │
│  ├── ChatInput (text, files, audio recording)                   │
│  ├── BrowserTabsPanel (view/edit tabs)                          │
│  ├── ModelSelector                                              │
│  ├── ToolSettings                                               │
│  └── VoiceRecorder                                              │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/SSE
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Python Backend (Port 8000)                      │
├─────────────────────────────────────────────────────────────────┤
│  Existing Endpoints:                                             │
│  ├── POST /v1/chat/completions (OpenAI-compatible, streaming)   │
│  ├── GET  /api/browser/tabs                                     │
│  └── GET  /api/browser/screenshot                               │
│                                                                  │
│  New Endpoints Needed:                                           │
│  ├── POST /api/chat/audio (native audio to Gemini)              │
│  ├── POST /api/tools/execute (run single tool)                  │
│  └── GET  /api/tools/list (available tools)                     │
│                                                                  │
│  Existing Features:                                              │
│  ├── LangGraph agent with 8 lab tools                           │
│  ├── API key rotation for rate limits                           │
│  ├── Playwright browser automation                              │
│  └── langchain-google-genai (native audio support)              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Installation Steps

### Phase 1: Create Next.js Project

```bash
# Create new Next.js app with TypeScript and Tailwind
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir

cd frontend

# Install AI SDK packages
pnpm add ai @ai-sdk/react

# Install OpenRouter provider (for topic naming + future models)
pnpm add @openrouter/ai-sdk-provider

# Install shadcn/ui for components
pnpm dlx shadcn@latest init

# Add UI components we need
pnpm dlx shadcn@latest add button input textarea card scroll-area select switch sheet badge separator avatar
```

### Phase 2: Environment Variables

Create `.env.local`:

```env
# Python backend URL
BACKEND_URL=http://localhost:8000

# OpenRouter API Key (for topic naming with FREE model)
# Get from: https://openrouter.ai/keys
# Free models available: nvidia/nemotron-3-nano-30b-a3b:free, google/gemma-2-9b-it:free
OPENROUTER_API_KEY=sk-or-v1-...

# Optional: Auth (disabled initially)
AUTH_DISABLED=true
```

**Note:** We use the same `OPENROUTER_API_KEY` that Lobechat was using. The topic naming model is `nvidia/nemotron-3-nano-30b-a3b:free` (completely free).

### Phase 3: Create API Routes

#### `/api/chat/route.ts` - Main Chat (Proxy to Python)

```typescript
import { type NextRequest } from 'next/server';

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { messages, model, enabledTools } = body;

  // Forward to Python backend
  const response = await fetch(`${process.env.BACKEND_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: model || 'lab-assistant',
      messages,
      stream: true,
      // Pass enabled tools filter
      tools: enabledTools,
    }),
  });

  // Stream response back to client
  return new Response(response.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
```

#### `/api/chat/title/route.ts` - Generate Chat Title (OpenRouter FREE)

```typescript
import { generateText } from 'ai';
import { createOpenRouter } from '@openrouter/ai-sdk-provider';

const openrouter = createOpenRouter({
  apiKey: process.env.OPENROUTER_API_KEY,
});

export async function POST(req: Request) {
  const { message } = await req.json();

  const { text } = await generateText({
    // Same FREE model as Lobechat was using
    model: openrouter('nvidia/nemotron-3-nano-30b-a3b:free'),
    prompt: `Generate a very short title (3-5 words, in Spanish) for a conversation that starts with: "${message}"`,
    maxTokens: 20,
  });

  return Response.json({ title: text.trim() });
}
```

#### `/api/chat/audio/route.ts` - Native Audio

```typescript
export async function POST(req: Request) {
  const formData = await req.formData();

  // Forward to Python backend which handles native Gemini audio
  const response = await fetch(`${process.env.BACKEND_URL}/api/chat/audio`, {
    method: 'POST',
    body: formData,
  });

  return new Response(response.body, {
    headers: { 'Content-Type': 'text/event-stream' },
  });
}
```

#### `/api/browser/tabs/route.ts` - Browser Tabs

```typescript
export async function GET() {
  const response = await fetch(`${process.env.BACKEND_URL}/api/browser/tabs`);
  return Response.json(await response.json());
}
```

#### `/api/tools/execute/route.ts` - Manual Tool Execution

```typescript
export async function POST(req: Request) {
  const { tool, args } = await req.json();

  const response = await fetch(`${process.env.BACKEND_URL}/api/tools/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool, args }),
  });

  return Response.json(await response.json());
}
```

### Phase 4: Create Chat Component

#### `src/components/chat.tsx`

```typescript
'use client';

import { useChat } from '@ai-sdk/react';
import { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card } from '@/components/ui/card';

export function Chat() {
  const [enabledTools, setEnabledTools] = useState<string[]>([
    'search_orders', 'get_order_results', 'get_order_info',
    'edit_results', 'edit_order_exams', 'create_new_order',
    'get_available_exams', 'ask_user'
  ]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { messages, input, handleInputChange, handleSubmit, status, error } = useChat({
    api: '/api/chat',
    body: { enabledTools },
    onFinish: async (message) => {
      // Generate title for new chats
      if (messages.length === 0) {
        const res = await fetch('/api/chat/title', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: input }),
        });
        const { title } = await res.json();
        console.log('Chat title:', title);
      }
    },
  });

  const handleFileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const files = fileInputRef.current?.files;

    handleSubmit(e, {
      experimental_attachments: files || undefined,
    });

    // Clear file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <Card key={message.id} className={`p-4 ${
            message.role === 'user' ? 'bg-blue-50 ml-12' : 'bg-gray-50 mr-12'
          }`}>
            <div className="font-semibold mb-1">
              {message.role === 'user' ? 'Tú' : 'Asistente'}
            </div>
            <div className="whitespace-pre-wrap">{message.content}</div>
          </Card>
        ))}

        {status === 'streaming' && (
          <div className="text-gray-500">Escribiendo...</div>
        )}

        {error && (
          <div className="text-red-500">Error: {error.message}</div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleFileSubmit} className="p-4 border-t">
        <div className="flex gap-2">
          <input
            type="file"
            ref={fileInputRef}
            multiple
            accept="image/*,.pdf"
            className="hidden"
          />
          <Button
            type="button"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
          >
            📎
          </Button>
          <Textarea
            value={input}
            onChange={handleInputChange}
            placeholder="Escribe un mensaje..."
            className="flex-1"
            rows={1}
          />
          <Button type="submit" disabled={status === 'streaming'}>
            Enviar
          </Button>
        </div>
      </form>
    </div>
  );
}
```

### Phase 5: Create Main Page

#### `src/app/page.tsx`

```typescript
import { Chat } from '@/components/chat';

export default function Home() {
  return (
    <main className="h-screen flex">
      {/* Sidebar - Chat History */}
      <aside className="w-64 border-r bg-gray-50 p-4">
        <h2 className="font-bold mb-4">Chats</h2>
        {/* Chat list will go here */}
      </aside>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <Chat />
      </div>

      {/* Right Panel - Browser Tabs (optional) */}
      {/* <aside className="w-80 border-l">
        <BrowserTabsPanel />
      </aside> */}
    </main>
  );
}
```

---

## Backend Changes Required

### New Endpoints to Add to `server.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat/audio` | POST | Accept audio file, send natively to Gemini |
| `/api/tools/execute` | POST | Execute single tool by name |
| `/api/tools/list` | GET | Return list of available tools |

### Modify `/v1/chat/completions`

Accept optional `tools` array to filter which tools the AI can use.

---

## Custom UI Components (Phase 2)

After basic chat works, add these components:

### 1. Model Selector

```typescript
// src/lib/models.ts
export const models = [
  { id: 'lab-assistant', name: 'Lab Assistant (Gemini)', provider: 'custom' },
  // Future: OpenRouter models
];

// src/components/model-selector.tsx
// Dropdown to select model, passed to useChat body
```

### 2. Tool Settings

```typescript
// src/lib/tools.ts
export const tools = [
  { id: 'search_orders', name: 'Buscar Órdenes', enabled: true },
  { id: 'get_order_results', name: 'Ver Resultados', enabled: true },
  // ... etc
];

// src/components/tool-settings.tsx
// Sheet/modal with switches to enable/disable each tool
```

### 3. Voice Recorder

```typescript
// src/components/voice-recorder.tsx
// Uses MediaRecorder API
// Records audio → sends to /api/chat/audio
```

### 4. Browser Tabs Panel

```typescript
// src/components/browser-tabs-panel.tsx
// Fetches from /api/browser/tabs
// Shows open tabs with patient info
// Click to expand and see/edit fields
// "Enviar Cambios" button → /api/tools/execute
```

---

## Migration Checklist

### Phase 1: Setup ✅
- [x] Create Next.js project with `create-next-app`
- [x] Install AI SDK packages (`ai`, `@ai-sdk/react`)
- [x] Install OpenRouter provider (`@openrouter/ai-sdk-provider`)
- [x] Initialize shadcn/ui
- [x] Add required UI components
- [x] Create `.env.local` with `BACKEND_URL` and `OPENROUTER_API_KEY`

### Phase 2: API Routes ✅
- [x] Create `/api/chat/route.ts` - proxy to Python backend
- [x] Create `/api/chat/title/route.ts` - generate titles with OpenRouter (FREE model)
- [x] Create `/api/browser/tabs/route.ts` - proxy browser tabs
- [x] Create `/api/tools/execute/route.ts` - manual tool execution
- [x] Test streaming works with Python backend

### Phase 3: Chat UI ✅
- [x] Create basic Chat component with useChat
- [x] Add message display
- [x] Add input with file attachment support
- [x] Add loading/error states
- [x] Test full chat flow

### Phase 4: Backend Updates (Partial)
- [ ] Add `/api/chat/audio` endpoint for native audio (backend needs update)
- [x] `/api/tools/execute` endpoint exists
- [ ] Add `/api/tools/list` endpoint
- [x] `/v1/chat/completions` accepts multimodal content

### Phase 5: Custom Features ✅
- [x] Add file preview thumbnails with remove button
- [x] Add Camera capture button
- [x] Add Voice Recorder component (MediaRecorder API)
- [x] Add image lightbox (click to expand)
- [x] Add audio/video players
- [ ] Add Browser Tabs Panel component
- [ ] Add Model Selector component
- [ ] Add Tool Settings component

### Phase 6: Database & Debug ✅
- [x] Chat message storage (file-based JSON database)
- [x] File attachment storage
- [x] Debug view for raw message inspection
- [ ] Chat history sidebar (load from database)

### Phase 7: Polish
- [ ] Responsive design
- [ ] Better error handling
- [ ] Loading states improvements

---

## Running the App

### Development

Terminal 1 - Python Backend:
```bash
cd backend
python server.py
# Runs on http://localhost:8000
```

Terminal 2 - Next.js Frontend:
```bash
cd frontend
pnpm dev
# Runs on http://localhost:3000
```

Or use `start-dev.bat` to launch both.

---

## Package Summary

### Required Packages

```json
{
  "dependencies": {
    "ai": "^6.x",
    "@ai-sdk/react": "^3.x",
    "@openrouter/ai-sdk-provider": "^1.x",
    "next": "^16.x",
    "react": "^19.x",
    "react-dom": "^19.x",
    "uuid": "^13.x"
  }
}
```

### shadcn/ui Components

```bash
pnpm dlx shadcn@latest add button input textarea card scroll-area select switch sheet badge separator avatar dropdown-menu
```

---

## Resources

- [AI SDK Documentation](https://ai-sdk.dev/docs/introduction)
- [AI SDK Providers](https://ai-sdk.dev/providers)
- [Google Generative AI Provider](https://ai-sdk.dev/providers/ai-sdk-providers/google-generative-ai)
- [OpenRouter Provider](https://ai-sdk.dev/providers/community-providers/openrouter)
- [useChat Reference](https://sdk.vercel.ai/docs/api-reference/use-chat)
- [shadcn/ui Components](https://ui.shadcn.com)
- [Next.js App Router](https://nextjs.org/docs/app)

---

## Sources

- [@openrouter/ai-sdk-provider - npm](https://www.npmjs.com/package/@openrouter/ai-sdk-provider)
- [OpenRouter Provider GitHub](https://github.com/OpenRouterTeam/ai-sdk-provider)
- [AI SDK Chatbot Example](https://ai-sdk.dev/elements/examples/chatbot)
- [Google Audio Understanding](https://ai.google.dev/gemini-api/docs/audio)
- [AI SDK Preview Attachments](https://github.com/vercel-labs/ai-sdk-preview-attachments)
