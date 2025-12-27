# Lab Assistant Migration - Coding Plan for Claude Code

## Overview
Migrate from custom SSE parsing to AI SDK Data Stream Protocol while keeping Python FastAPI backend. Add auth, PWA, remote access, and mobile UI.

---

## PHASE 1: Backend - AI SDK Data Stream Protocol

### 1.1 Create StreamAdapter class in `backend/stream_adapter.py`
```python
import json
from typing import Any, List

class StreamAdapter:
    """Converts LangGraph events to AI SDK Data Stream Protocol v1"""
    
    @staticmethod
    def text(chunk: str) -> str:
        return f'0:{json.dumps(chunk)}\n'
    
    @staticmethod
    def data(payload: List[Any]) -> str:
        return f'2:{json.dumps(payload)}\n'
    
    @staticmethod
    def tool_call(tool_call_id: str, tool_name: str, args: dict) -> str:
        return f'9:{json.dumps({"toolCallId": tool_call_id, "toolName": tool_name, "args": args})}\n'
    
    @staticmethod
    def tool_result(tool_call_id: str, result: Any) -> str:
        return f'a:{json.dumps({"toolCallId": tool_call_id, "result": result})}\n'
    
    @staticmethod
    def error(message: str) -> str:
        return f'3:{json.dumps(message)}\n'
    
    @staticmethod
    def finish(usage: dict = None) -> str:
        payload = {"finishReason": "stop"}
        if usage:
            payload["usage"] = usage
        return f'd:{json.dumps(payload)}\n'
```

### 1.2 Refactor `backend/server.py` `/v1/chat/completions` endpoint
- Replace custom SSE format with StreamAdapter
- Remove OpenAI compatibility wrapper - use native protocol
- Key changes:
  - Set header: `"x-vercel-ai-data-stream": "v1"`
  - Yield `StreamAdapter.text(chunk)` for LLM tokens
  - Yield `StreamAdapter.tool_call()` on `on_tool_start`
  - Yield `StreamAdapter.tool_result()` on `on_tool_end`
  - Yield `StreamAdapter.data([{tabs_context}])` for browser state updates
  - End with `StreamAdapter.finish()`

### 1.3 Create new endpoint `POST /api/chat` (simplified)
```python
@app.post("/api/chat")
async def chat_stream(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    chat_id = body.get("chatId")
    
    async def generate():
        async for event in graph.astream_events({"messages": messages}, config, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and chunk.content:
                    yield StreamAdapter.text(chunk.content)
            elif event["event"] == "on_tool_start":
                yield StreamAdapter.tool_call(event["run_id"], event["name"], event["data"]["input"])
            elif event["event"] == "on_tool_end":
                yield StreamAdapter.tool_result(event["run_id"], event["data"]["output"])
        yield StreamAdapter.finish()
    
    return StreamingResponse(generate(), media_type="text/plain",
        headers={"x-vercel-ai-data-stream": "v1", "Cache-Control": "no-cache"})
```

---

## PHASE 2: Frontend - AI SDK Integration

### 2.1 Simplify `frontend/src/app/api/chat/route.ts`
- Remove manual SSE parsing (`parseOpenAIStream`)
- Use direct proxy to FastAPI with headers pass-through
- Let AI SDK handle stream parsing on client

```typescript
export async function POST(req: NextRequest) {
  const body = await req.json();
  const { messages, chatId } = body;
  
  // Get or create chat
  let actualChatId = chatId;
  if (!chatId) {
    const chat = await createChat('Nuevo Chat');
    actualChatId = chat.id;
  }
  
  // Store user message
  const lastMsg = messages[messages.length - 1];
  if (lastMsg?.role === 'user') {
    await addMessage(actualChatId, 'user', getTextContent(lastMsg));
  }
  
  // Proxy to FastAPI - let AI SDK parse the stream on frontend
  const response = await fetch(`${process.env.BACKEND_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, chatId: actualChatId }),
  });
  
  return new Response(response.body, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'X-Chat-Id': actualChatId,
      'x-vercel-ai-data-stream': 'v1',
    },
  });
}
```

### 2.2 Update `frontend/src/components/chat.tsx`
- Remove `parseOpenAIStream` function
- Remove `createUIMessageStream` wrapper
- Use `useChat` with `fetch` transport pointing to `/api/chat`
- Add `reload()` for message regeneration

```typescript
const { messages, sendMessage, status, error, reload, setMessages } = useChat({
  api: '/api/chat',
  id: chatId,
  initialMessages: loadedMessages,
  body: { chatId },
  onFinish: async (message) => {
    // Save assistant message to DB
    await fetch(`/api/db/chats/${chatId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: 'assistant', content: message.content }),
    });
    // Generate title if first exchange
    if (messages.length === 1) {
      generateTitle(messages[0].content, chatId);
    }
  },
});
```

### 2.3 Add Regenerate button to chat UI
```tsx
{message.role === 'assistant' && (
  <Button variant="ghost" size="sm" onClick={() => reload()}>
    <RefreshCcw className="h-4 w-4" /> Reintentar
  </Button>
)}
```

---

## PHASE 3: Database Migration (SQLite → PostgreSQL-ready)

### 3.1 Install Drizzle ORM
```bash
cd frontend
pnpm add drizzle-orm postgres
pnpm add -D drizzle-kit @types/pg
```

### 3.2 Create schema `frontend/src/lib/db/schema.ts`
```typescript
import { pgTable, uuid, text, timestamp, jsonb, integer } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: uuid('id').primaryKey().defaultRandom(),
  email: text('email').notNull().unique(),
  name: text('name'),
  createdAt: timestamp('created_at').defaultNow(),
});

export const chats = pgTable('chats', {
  id: uuid('id').primaryKey().defaultRandom(),
  userId: uuid('user_id').references(() => users.id),
  title: text('title').default('Nuevo Chat'),
  createdAt: timestamp('created_at').defaultNow(),
  updatedAt: timestamp('updated_at').defaultNow(),
});

export const messages = pgTable('messages', {
  id: uuid('id').primaryKey().defaultRandom(),
  chatId: uuid('chat_id').references(() => chats.id).notNull(),
  role: text('role').notNull(), // 'user' | 'assistant' | 'system'
  content: text('content'),
  parts: jsonb('parts'), // For multimodal: [{type: 'text', text: ''}, {type: 'image', ...}]
  orderIndex: integer('order_index').notNull(),
  createdAt: timestamp('created_at').defaultNow(),
});

export const files = pgTable('files', {
  id: uuid('id').primaryKey().defaultRandom(),
  messageId: uuid('message_id').references(() => messages.id),
  filename: text('filename').notNull(),
  mimeType: text('mime_type').notNull(),
  path: text('path').notNull(),
  size: integer('size'),
  createdAt: timestamp('created_at').defaultNow(),
});
```

### 3.3 Keep SQLite for now, structure for easy migration
- Continue using `better-sqlite3` locally
- Structure queries to be easily portable to Drizzle+Postgres later
- Add `userId` column to chats table (nullable until auth added)

---

## PHASE 4: Authentication - NextAuth.js v5

### 4.1 Install dependencies
```bash
pnpm add next-auth@beta @auth/drizzle-adapter
```

### 4.2 Create `frontend/auth.ts`
```typescript
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

// Email whitelist - can also load from env or file
const ALLOWED_EMAILS = process.env.ALLOWED_EMAILS?.split(',') || [];

export const { auth, handlers, signIn, signOut } = NextAuth({
  providers: [Google],
  callbacks: {
    async signIn({ user, profile }) {
      // Require verified email
      if (!(profile as any)?.email_verified) return false;
      // Check whitelist
      if (ALLOWED_EMAILS.length > 0 && !ALLOWED_EMAILS.includes(user.email!)) {
        return '/auth/denied';
      }
      return true;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub!;
      }
      return session;
    },
  },
  pages: {
    signIn: '/login',
    error: '/auth/error',
  },
});
```

### 4.3 Create auth API route `frontend/src/app/api/auth/[...nextauth]/route.ts`
```typescript
export { handlers as GET, handlers as POST } from "@/auth";
```

### 4.4 Create middleware `frontend/middleware.ts`
```typescript
import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const isLoggedIn = !!req.auth;
  const isAuthPage = req.nextUrl.pathname.startsWith('/login');
  const isApiAuth = req.nextUrl.pathname.startsWith('/api/auth');
  
  // Allow auth endpoints
  if (isApiAuth) return NextResponse.next();
  
  // Redirect to login if not authenticated
  if (!isLoggedIn && !isAuthPage) {
    return NextResponse.redirect(new URL('/login', req.url));
  }
  
  // Redirect to home if already logged in and on login page
  if (isLoggedIn && isAuthPage) {
    return NextResponse.redirect(new URL('/', req.url));
  }
  
  return NextResponse.next();
});

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|api/files).*)'],
};
```

### 4.5 Create login page `frontend/src/app/login/page.tsx`
```tsx
import { signIn } from "@/auth";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-4">
        <h1 className="text-2xl font-bold">Lab Assistant</h1>
        <form action={async () => { "use server"; await signIn("google"); }}>
          <Button type="submit">Iniciar sesión con Google</Button>
        </form>
      </div>
    </div>
  );
}
```

### 4.6 Environment variables needed
```env
AUTH_SECRET=<generate with: npx auth secret>
AUTH_GOOGLE_ID=<from Google Cloud Console>
AUTH_GOOGLE_SECRET=<from Google Cloud Console>
ALLOWED_EMAILS=admin@example.com,user@example.com
```

---

## PHASE 5: Mobile-Responsive UI

### 5.1 Install shadcn/ui Sidebar
```bash
npx shadcn@latest add sidebar sheet
```

### 5.2 Create responsive layout `frontend/src/app/layout.tsx`
```tsx
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset className="flex flex-col h-dvh">
            {children}
          </SidebarInset>
        </SidebarProvider>
      </body>
    </html>
  );
}
```

### 5.3 Create `frontend/src/components/app-sidebar.tsx`
```tsx
"use client";
import { Sidebar, SidebarContent, SidebarHeader, SidebarMenu, SidebarMenuItem, 
         SidebarMenuButton, SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useMediaQuery } from "@/hooks/use-media-query";

export function AppSidebar({ chats, selectedId, onSelect, onNewChat }) {
  const isMobile = useMediaQuery("(max-width: 768px)");
  const { open, setOpen } = useSidebar();
  
  const content = (
    <>
      <SidebarHeader className="p-4">
        <Button onClick={onNewChat} className="w-full">+ Nuevo Chat</Button>
      </SidebarHeader>
      <SidebarContent>
        <SidebarMenu>
          {chats.map((chat) => (
            <SidebarMenuItem key={chat.id}>
              <SidebarMenuButton 
                isActive={selectedId === chat.id}
                onClick={() => { onSelect(chat.id); if (isMobile) setOpen(false); }}
              >
                {chat.title}
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarContent>
    </>
  );
  
  if (isMobile) {
    return (
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="fixed top-2 left-2 z-50">
            ☰
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="p-0 w-72">
          {content}
        </SheetContent>
      </Sheet>
    );
  }
  
  return <Sidebar collapsible="icon">{content}</Sidebar>;
}
```

### 5.4 Create `frontend/src/hooks/use-media-query.ts`
```typescript
import { useState, useEffect } from 'react';

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);
  
  useEffect(() => {
    const media = window.matchMedia(query);
    setMatches(media.matches);
    const listener = (e: MediaQueryListEvent) => setMatches(e.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, [query]);
  
  return matches;
}
```

### 5.5 Update chat input for mobile
```tsx
// Fixed bottom input with safe area
<div className="sticky bottom-0 p-4 pb-[env(safe-area-inset-bottom)] border-t bg-background">
  <div className="flex gap-2 max-w-4xl mx-auto">
    <Textarea className="min-h-[44px]" /> {/* 44px min touch target */}
    <Button className="h-11 px-6">Enviar</Button>
  </div>
</div>
```

---

## PHASE 6: Model Picker

### 6.1 Create model config `frontend/src/lib/models.ts`
```typescript
export const AVAILABLE_MODELS = [
  { id: 'google/gemini-2.5-flash', name: 'Gemini 2.5 Flash', provider: 'Google', free: false },
  { id: 'google/gemini-2.0-flash-exp:free', name: 'Gemini 2.0 Flash (Free)', provider: 'Google', free: true },
  { id: 'anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', provider: 'Anthropic', free: false },
  { id: 'meta-llama/llama-3.3-70b-instruct:free', name: 'Llama 3.3 70B (Free)', provider: 'Meta', free: true },
  { id: 'openai/gpt-4o-mini', name: 'GPT-4o Mini', provider: 'OpenAI', free: false },
] as const;

export type ModelId = typeof AVAILABLE_MODELS[number]['id'];
```

### 6.2 Create `frontend/src/components/model-selector.tsx`
```tsx
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AVAILABLE_MODELS, ModelId } from "@/lib/models";

export function ModelSelector({ value, onChange }: { value: ModelId; onChange: (v: ModelId) => void }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-[200px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {AVAILABLE_MODELS.map((m) => (
          <SelectItem key={m.id} value={m.id}>
            {m.name} {m.free && '✨'}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

### 6.3 Pass model to API
```typescript
// In chat.tsx
const [selectedModel, setSelectedModel] = useState<ModelId>('google/gemini-2.5-flash');

const { messages, sendMessage } = useChat({
  api: '/api/chat',
  body: { chatId, model: selectedModel },
});
```

### 6.4 Update FastAPI to use model from request
```python
# In backend - switch to OpenRouter for all models
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

@app.post("/api/chat")
async def chat(request: dict):
    model = request.get("model", "google/gemini-2.5-flash")
    # Use model with LangGraph or direct OpenRouter call
```

---

## PHASE 7: PWA Setup

### 7.1 Install PWA package
```bash
pnpm add @ducanh2912/next-pwa
```

### 7.2 Update `frontend/next.config.ts`
```typescript
import withPWA from '@ducanh2912/next-pwa';

const nextConfig = withPWA({
  dest: 'public',
  disable: process.env.NODE_ENV === 'development',
  register: true,
  skipWaiting: true,
  fallbacks: { document: '/offline' },
})({
  // existing config
});

export default nextConfig;
```

### 7.3 Create `frontend/src/app/manifest.ts`
```typescript
import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Lab Assistant AI',
    short_name: 'LabAI',
    description: 'Asistente de laboratorio para entrada de resultados',
    start_url: '/',
    display: 'standalone',
    background_color: '#ffffff',
    theme_color: '#0a0a0a',
    icons: [
      { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
      { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  };
}
```

### 7.4 Create offline page `frontend/src/app/offline/page.tsx`
```tsx
export default function OfflinePage() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-2xl font-bold">Sin conexión</h1>
        <p>Verifica tu conexión a internet</p>
      </div>
    </div>
  );
}
```

### 7.5 Add icons
- Create `public/icon-192.png` (192x192)
- Create `public/icon-512.png` (512x512)

---

## PHASE 8: Remote Access (Cloudflare Tunnel)

### 8.1 Install cloudflared (one-time on server PC)
```bash
# Windows (winget)
winget install Cloudflare.cloudflared

# Or download from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
```

### 8.2 Quick tunnel (for testing)
```bash
cloudflared tunnel --url http://localhost:3000
# Gives you a random *.trycloudflare.com URL
```

### 8.3 Persistent tunnel with custom domain (requires Cloudflare account + domain)
```bash
cloudflared tunnel login
cloudflared tunnel create lab-assistant
cloudflared tunnel route dns lab-assistant lab.yourdomain.com
```

### 8.4 Create config `~/.cloudflared/config.yml`
```yaml
tunnel: lab-assistant
credentials-file: C:\Users\<you>\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: lab.yourdomain.com
    service: http://localhost:3000
  - service: http_status:404
```

### 8.5 Run as Windows service
```bash
cloudflared service install
cloudflared service start
```

### 8.6 Add to `start-dev.bat`
```batch
:: Start Cloudflare Tunnel
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel run lab-assistant"
```

---

## PHASE 9: Prevent Search Indexing

### 9.1 Create `frontend/src/app/robots.ts`
```typescript
import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', disallow: '/' },
  };
}
```

### 9.2 Add meta tags in `frontend/src/app/layout.tsx`
```typescript
export const metadata: Metadata = {
  title: 'Lab Assistant AI',
  robots: { index: false, follow: false, nocache: true },
};
```

### 9.3 Add headers in `frontend/next.config.ts`
```typescript
async headers() {
  return [{
    source: '/:path*',
    headers: [{ key: 'X-Robots-Tag', value: 'noindex, nofollow, noarchive' }],
  }];
}
```

---

## Implementation Order

1. **Phase 1** (Backend StreamAdapter) - 2 hours
2. **Phase 2** (Frontend AI SDK) - 3 hours  
3. **Phase 5** (Mobile UI) - 2 hours
4. **Phase 6** (Model Picker) - 1 hour
5. **Phase 4** (Auth) - 2 hours
6. **Phase 7** (PWA) - 1 hour
7. **Phase 8** (Cloudflare) - 30 min
8. **Phase 9** (No-index) - 15 min
9. **Phase 3** (DB migration) - Later, when scaling

---

## Testing Checklist

- [ ] Stream protocol works (text chunks appear in real-time)
- [ ] Tool calls visible in UI during execution
- [ ] Message regeneration (`reload()`) works
- [ ] New chats created on first message
- [ ] Title generated after first exchange
- [ ] Google login works
- [ ] Non-whitelisted emails rejected
- [ ] Sidebar collapses on mobile
- [ ] Chat input stays at bottom on mobile keyboard
- [ ] PWA installable (check DevTools > Application)
- [ ] Cloudflare tunnel accessible from phone
- [ ] Google cannot index (check robots.txt)

---

## Files to Create/Modify Summary

### New Files
- `backend/stream_adapter.py`
- `frontend/auth.ts`
- `frontend/middleware.ts`
- `frontend/src/app/login/page.tsx`
- `frontend/src/app/manifest.ts`
- `frontend/src/app/robots.ts`
- `frontend/src/app/offline/page.tsx`
- `frontend/src/components/app-sidebar.tsx`
- `frontend/src/components/model-selector.tsx`
- `frontend/src/hooks/use-media-query.ts`
- `frontend/src/lib/models.ts`
- `frontend/src/lib/db/schema.ts`

### Modify Files
- `backend/server.py` - StreamAdapter integration
- `frontend/src/app/api/chat/route.ts` - Simplify to proxy
- `frontend/src/components/chat.tsx` - Remove SSE parsing, add reload
- `frontend/src/app/layout.tsx` - SidebarProvider, metadata
- `frontend/src/app/page.tsx` - Use new sidebar
- `frontend/next.config.ts` - PWA + headers
- `frontend/.env.local` - Auth secrets, allowed emails
