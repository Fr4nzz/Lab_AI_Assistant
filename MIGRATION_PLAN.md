# Migration Plan: Next.js to Nuxt AI Chatbot Template

## Executive Summary

This plan outlines migrating from the current **Next.js + React** frontend to the **Nuxt AI Chatbot Template** using Vue and Nuxt UI.

### Current Stack → Target Stack

| Aspect | Current (Next.js) | Target (Nuxt) |
|--------|-------------------|---------------|
| Framework | Next.js 16 + React 19 | Nuxt 3 + Vue 3 |
| UI Library | shadcn/ui + Radix UI | Nuxt UI v4 (built-in chat components) |
| AI SDK | `@ai-sdk/react` v3 + `ai` v6 | `@ai-sdk/vue` v2 + `ai` v5 |
| Database | SQLite + Drizzle ORM | SQLite (better-sqlite3) + Drizzle ORM |
| Auth | NextAuth v5 (Google OAuth) | nuxt-auth-utils (Google OAuth) |
| Styling | Tailwind CSS v4 | Tailwind CSS (via Nuxt UI) |
| PWA | next-pwa | @vite-pwa/nuxt (optional) |

---

## 🆕 Template Analysis (After Installation)

The Nuxt AI Chatbot template has been installed at `frontend-nuxt/`. Key findings:

### Template Directory Structure
```
frontend-nuxt/
├── app/                          # Frontend application
│   ├── assets/css/main.css       # TailwindCSS + Nuxt UI theme
│   ├── components/
│   │   ├── DashboardNavbar.vue   # Top navigation bar
│   │   ├── DragDropOverlay.vue   # Drag-drop file indicator
│   │   ├── FileAvatar.vue        # File preview with status
│   │   ├── FileUploadButton.vue  # Upload trigger button
│   │   ├── ModelSelect.vue       # AI model selector
│   │   ├── Reasoning.vue         # Collapsible thinking display
│   │   ├── UserMenu.vue          # User profile dropdown
│   │   ├── prose/PreStream.vue   # Streaming code highlighter
│   │   └── tool/
│   │       ├── Chart.vue         # Chart visualization
│   │       └── Weather.vue       # Weather tool display
│   ├── composables/
│   │   ├── useChats.ts           # Chat grouping by date
│   │   ├── useFileUpload.ts      # File upload with status
│   │   ├── useHighlighter.ts     # Shiki code highlighting
│   │   └── useModels.ts          # Model selection
│   ├── layouts/default.vue       # Main layout with sidebar
│   ├── pages/
│   │   ├── index.vue             # Home/chat creation
│   │   └── chat/[id].vue         # Chat detail page
│   └── app.config.ts             # Color theme config
├── server/
│   ├── api/
│   │   ├── chats.get.ts          # List chats
│   │   ├── chats.post.ts         # Create chat
│   │   └── chats/[id]/
│   │       ├── index.get.ts      # Get chat
│   │       ├── index.post.ts     # Send message (stream)
│   │       └── index.delete.ts   # Delete chat
│   ├── routes/auth/github.get.ts # OAuth handler
│   └── db/schema.ts              # Drizzle schema
├── shared/
│   ├── types/                    # TypeScript types
│   └── utils/
│       └── tools/                # Tool definitions
├── nuxt.config.ts                # Nuxt configuration
└── package.json                  # Dependencies
```

### Key Template Features to Leverage

1. **UChatMessages Component** - Built-in message list with:
   - Auto-scroll on streaming
   - Message status indicators
   - User/assistant styling variants
   - Parts-based rendering (text, reasoning, tools, files)

2. **UChatPrompt Component** - Input area with:
   - Auto-resize textarea
   - File upload slots (header/footer)
   - Loading/disabled states
   - Submit/stop/reload buttons

3. **UDashboardSidebar** - Collapsible sidebar with:
   - Chat history grouped by date (Today, Yesterday, Last week, etc.)
   - Search functionality
   - Delete buttons on hover
   - User menu with theme settings

4. **Built-in Composables**:
   - `useChats()` - Groups chats by date
   - `useFileUpload()` - Handles file uploads with status tracking
   - `useModels()` - Model selection with cookie persistence
   - `useHighlighter()` - Shiki syntax highlighting

### Backend Integration Points

The Python backend already has `/api/chat/aisdk` endpoint that:
- Streams in AI SDK Data Stream Protocol v1 format
- Sends tool calls with parameters: `tool_status(tool_name, "start", tool_input)`
- Sends tool results: `tool_status(tool_name, "end")`
- Includes usage stats in the stream

**No backend changes needed** - just proxy from Nuxt to Python backend.

### Key Differences from Current Frontend

| Feature | Current (Next.js) | Template (Nuxt) |
|---------|-------------------|-----------------|
| Tool display | Console logs only | UI display via UChatMessage parts |
| File upload | Custom implementation | Built-in useFileUpload composable |
| Chat grouping | Manual | useChats() composable (Today, Yesterday, etc.) |
| Code highlighting | react-markdown | Shiki with streaming support |
| Theme switching | Manual | Built-in UserMenu with color picker |

---

## Key Benefits of Migration

1. **Purpose-Built Chat Components**: Nuxt UI provides `UChatMessage`, `UChatMessages`, `UChatPrompt` components designed specifically for AI chatbots
2. **Simplified Code**: Vue's composition API + Nuxt's auto-imports reduce boilerplate
3. **Better Streaming**: Nuxt UI components have built-in support for AI SDK streaming
4. **Command Palette**: Built-in command palette with keyboard shortcuts
5. **Dark/Light Mode**: Native theme support out of the box
6. **Collapsible Sidebar**: Pre-built responsive sidebar component

---

## Phase 1: Project Setup & Foundation

### 1.1 Create New Nuxt Project

```bash
# In Lab_AI_Assistant directory
npx nuxi@latest init -t ui/chat frontend-nuxt
cd frontend-nuxt
pnpm install
```

### 1.2 Install Additional Dependencies

```bash
# AI SDK for Vue
pnpm add @ai-sdk/vue ai

# OpenRouter provider (for your LLM integration)
pnpm add @openrouter/ai-sdk-provider

# Database (Drizzle + SQLite)
pnpm add drizzle-orm better-sqlite3
pnpm add -D drizzle-kit @types/better-sqlite3

# Auth utils
pnpm add nuxt-auth-utils
```

### 1.3 Environment Variables Setup

Create `.env` file with:

```env
# Database
DATABASE_URL=file:./data/lab-assistant.db

# AI Configuration (migrate from current)
OPENROUTER_API_KEY=your_openrouter_key

# Backend URL (Python backend)
BACKEND_URL=http://localhost:8000

# Authentication (change from Google to GitHub, or keep Google)
NUXT_SESSION_PASSWORD=your-32-char-minimum-session-password
NUXT_OAUTH_GOOGLE_CLIENT_ID=your_google_client_id
NUXT_OAUTH_GOOGLE_CLIENT_SECRET=your_google_client_secret

# Optional: Allowed emails whitelist
ALLOWED_EMAILS=user1@email.com,user2@email.com
```

---

## Phase 2: Database Schema Migration

### 2.1 Migrate Drizzle Schema

The current schema can be largely reused. Create `server/database/schema.ts`:

```typescript
import { sqliteTable, text, integer } from 'drizzle-orm/sqlite-core'
import { relations } from 'drizzle-orm'

export const users = sqliteTable('users', {
  id: text('id').primaryKey(),
  email: text('email').notNull().unique(),
  name: text('name'),
  image: text('image'),
  createdAt: text('created_at').default(sql`CURRENT_TIMESTAMP`)
})

export const chats = sqliteTable('chats', {
  id: text('id').primaryKey(),
  userId: text('user_id').references(() => users.id),
  title: text('title'),
  createdAt: text('created_at').default(sql`CURRENT_TIMESTAMP`),
  updatedAt: text('updated_at')
})

export const messages = sqliteTable('messages', {
  id: text('id').primaryKey(),
  chatId: text('chat_id').references(() => chats.id, { onDelete: 'cascade' }),
  role: text('role').notNull(), // 'user' | 'assistant' | 'system'
  content: text('content'),
  rawContent: text('raw_content'), // JSON for multimodal parts
  orderIndex: integer('order_index'),
  metadata: text('metadata'), // JSON for model, tokens, etc.
  createdAt: text('created_at').default(sql`CURRENT_TIMESTAMP`)
})

export const files = sqliteTable('files', {
  id: text('id').primaryKey(),
  messageId: text('message_id').references(() => messages.id, { onDelete: 'cascade' }),
  filename: text('filename'),
  mimeType: text('mime_type'),
  path: text('path'),
  size: integer('size'),
  createdAt: text('created_at').default(sql`CURRENT_TIMESTAMP`)
})

// Relations
export const chatsRelations = relations(chats, ({ one, many }) => ({
  user: one(users, { fields: [chats.userId], references: [users.id] }),
  messages: many(messages)
}))

export const messagesRelations = relations(messages, ({ one, many }) => ({
  chat: one(chats, { fields: [messages.chatId], references: [chats.id] }),
  files: many(files)
}))
```

### 2.2 Database Migration Script

Create `server/utils/migrate-data.ts` to migrate existing data:

```typescript
// Script to copy data from old SQLite to new structure
// Run once during migration
```

---

## Phase 3: Authentication Migration

### 3.1 Setup nuxt-auth-utils

Add to `nuxt.config.ts`:

```typescript
export default defineNuxtConfig({
  modules: ['@nuxt/ui', 'nuxt-auth-utils'],
  runtimeConfig: {
    session: {
      password: process.env.NUXT_SESSION_PASSWORD
    },
    oauth: {
      google: {
        clientId: process.env.NUXT_OAUTH_GOOGLE_CLIENT_ID,
        clientSecret: process.env.NUXT_OAUTH_GOOGLE_CLIENT_SECRET
      }
    }
  }
})
```

### 3.2 Create OAuth Handler

Create `server/routes/auth/google.get.ts`:

```typescript
export default defineOAuthGoogleEventHandler({
  async onSuccess(event, { user }) {
    // Check allowed emails if configured
    const allowedEmails = process.env.ALLOWED_EMAILS?.split(',')
    if (allowedEmails && !allowedEmails.includes(user.email)) {
      throw createError({ statusCode: 403, message: 'Email not authorized' })
    }

    // Create/update user in database
    await upsertUser({
      id: user.sub,
      email: user.email,
      name: user.name,
      image: user.picture
    })

    await setUserSession(event, { user })
    return sendRedirect(event, '/')
  }
})
```

### 3.3 Authentication Middleware

Create `server/middleware/auth.ts`:

```typescript
export default defineEventHandler(async (event) => {
  const publicPaths = ['/auth', '/login', '/api/auth']
  if (publicPaths.some(p => event.path.startsWith(p))) return

  const session = await getUserSession(event)
  if (!session?.user) {
    return sendRedirect(event, '/login')
  }
})
```

---

## Phase 4: API Routes Migration

### 4.1 Chat API Structure

Create the following API routes:

```
server/
├── api/
│   ├── chats/
│   │   ├── index.get.ts      # List all chats
│   │   ├── index.post.ts     # Create new chat
│   │   └── [id]/
│   │       ├── index.get.ts  # Get chat details
│   │       ├── index.post.ts # Send message (stream)
│   │       ├── index.patch.ts # Update chat
│   │       └── index.delete.ts # Delete chat
│   ├── files/
│   │   └── [filename].get.ts # Serve uploaded files
│   └── models/
│       └── index.get.ts      # List available models
```

### 4.2 Main Chat Streaming Endpoint

Create `server/api/chats/[id].post.ts`:

```typescript
export default defineEventHandler(async (event) => {
  const chatId = getRouterParam(event, 'id')
  const { messages, model, enabledTools, showStats = true } = await readBody(event)

  // Get session for user context
  const session = await getUserSession(event)

  // Get chat to verify ownership
  const chat = await getChat(chatId)
  if (!chat) {
    throw createError({ statusCode: 404, message: 'Chat not found' })
  }

  // Save user message to database BEFORE streaming
  const lastMessage = messages[messages.length - 1]
  if (lastMessage?.role === 'user') {
    const textContent = extractTextContent(lastMessage)
    await addMessage({
      id: generateId(),
      chatId,
      role: 'user',
      content: textContent,
      parts: JSON.stringify(lastMessage.parts || []),
      createdAt: new Date().toISOString()
    })

    // Generate title for new chats (fire and forget)
    if (!chat.title || chat.title === 'Nuevo Chat') {
      generateTitle(chatId, textContent).catch(console.error)
    }
  }

  // Convert messages to backend format (multimodal support)
  const backendMessages = convertMessagesForBackend(messages)

  // Proxy to Python backend
  const backendUrl = useRuntimeConfig().backendUrl || 'http://localhost:8000'

  const response = await $fetch.raw(`${backendUrl}/api/chat/aisdk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: {
      messages: backendMessages,
      chatId,
      model: model || 'lab-assistant',
      tools: enabledTools,
      showStats
    },
    responseType: 'stream'
  })

  // Collect response while streaming for database storage
  const reader = response.body?.getReader()
  if (!reader) throw createError({ statusCode: 500, message: 'No response body' })

  let fullResponse = ''

  const stream = new ReadableStream({
    async start(controller) {
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        controller.enqueue(value)

        // Parse stream to collect text for storage
        const text = decoder.decode(value, { stream: true })
        for (const line of text.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const parsed = JSON.parse(line.slice(6))
              if (parsed.type === 'text-delta' && parsed.delta) {
                fullResponse += parsed.delta
              }
            } catch {}
          }
        }
      }

      controller.close()

      // Save assistant response to database
      if (fullResponse) {
        await addMessage({
          id: generateId(),
          chatId,
          role: 'assistant',
          content: fullResponse,
          createdAt: new Date().toISOString()
        })
      }
    }
  })

  // Return stream with AI SDK headers
  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'x-vercel-ai-ui-message-stream': 'v1',
      'X-Chat-Id': chatId,
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    }
  })
})

// Helper: Extract text content from message
function extractTextContent(message: any): string {
  if (typeof message.content === 'string') return message.content
  if (message.parts) {
    return message.parts
      .filter((p: any) => p.type === 'text')
      .map((p: any) => p.text)
      .join('')
  }
  return ''
}

// Helper: Convert messages for backend (handle multimodal)
function convertMessagesForBackend(messages: any[]) {
  return messages.map(msg => {
    if (typeof msg.content === 'string') {
      return { role: msg.role, content: msg.content }
    }

    if (msg.parts) {
      const hasMedia = msg.parts.some((p: any) =>
        ['file', 'image', 'audio'].includes(p.type)
      )

      if (hasMedia) {
        const content = msg.parts.map((part: any) => {
          if (part.type === 'text') return { type: 'text', text: part.text }
          if (part.mimeType?.startsWith('audio/') || part.mimeType?.startsWith('video/')) {
            return { type: 'media', data: part.data, mime_type: part.mimeType }
          }
          if (part.url) {
            return { type: 'image_url', image_url: { url: part.url } }
          }
          return null
        }).filter(Boolean)

        return { role: msg.role, content }
      }

      const textContent = msg.parts
        .filter((p: any) => p.type === 'text')
        .map((p: any) => p.text)
        .join('')
      return { role: msg.role, content: textContent }
    }

    return { role: msg.role, content: '' }
  })
}
```

### 4.3 Database Operations

Create `server/utils/db.ts`:

```typescript
import { drizzle } from 'drizzle-orm/better-sqlite3'
import Database from 'better-sqlite3'
import * as schema from '../database/schema'

const sqlite = new Database('./data/lab-assistant.db')
export const db = drizzle(sqlite, { schema })

export async function getChats(userId?: string) {
  return db.query.chats.findMany({
    where: userId ? eq(schema.chats.userId, userId) : undefined,
    with: { messages: true },
    orderBy: desc(schema.chats.updatedAt)
  })
}

export async function getChat(chatId: string) {
  return db.query.chats.findFirst({
    where: eq(schema.chats.id, chatId),
    with: { messages: { orderBy: asc(schema.messages.orderIndex) } }
  })
}

export async function createChat(data: NewChat) {
  return db.insert(schema.chats).values(data).returning()
}

export async function addMessage(data: NewMessage) {
  return db.insert(schema.messages).values(data).returning()
}

// ... more CRUD operations
```

---

## Phase 5: Frontend Components Migration

### 5.1 Main Layout

Create `app/app.vue`:

```vue
<template>
  <UApp>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
```

### 5.2 Chat Page

Create `app/pages/chat/[id].vue`:

```vue
<script setup lang="ts">
import { Chat } from '@ai-sdk/vue'

const route = useRoute()
const chatId = computed(() => route.params.id as string)

// Load existing messages
const { data: chatData } = await useFetch(`/api/chats/${chatId.value}`)

// Initialize chat with AI SDK
const chat = new Chat({
  api: `/api/chats/${chatId.value}`,
  initialMessages: chatData.value?.messages || []
})

const { messages, input, status, handleSubmit, stop } = chat
</script>

<template>
  <div class="flex flex-col h-screen">
    <!-- Chat Messages -->
    <UChatMessages
      :messages="messages"
      :status="status"
      class="flex-1 overflow-y-auto p-4"
    >
      <template #message="{ message }">
        <UChatMessage
          :id="message.id"
          :role="message.role"
          :parts="message.parts"
          :side="message.role === 'user' ? 'right' : 'left'"
          :variant="message.role === 'user' ? 'soft' : 'naked'"
          :avatar="message.role === 'assistant' ? { icon: 'i-lucide-bot' } : undefined"
        />
      </template>
    </UChatMessages>

    <!-- Chat Input -->
    <div class="border-t p-4">
      <UChatPrompt
        v-model="input"
        :loading="status === 'streaming'"
        placeholder="Escribe tu mensaje..."
        @submit="handleSubmit"
      />
    </div>
  </div>
</template>
```

### 5.3 Sidebar with Chat History

Create `app/components/ChatSidebar.vue`:

```vue
<script setup lang="ts">
const { data: chats, refresh } = await useFetch('/api/chats')

const selectedChat = useState<string>('selectedChat')

async function createNewChat() {
  const { data } = await useFetch('/api/chats', { method: 'POST' })
  if (data.value) {
    await refresh()
    navigateTo(`/chat/${data.value.id}`)
  }
}

async function deleteChat(chatId: string) {
  await useFetch(`/api/chats/${chatId}`, { method: 'DELETE' })
  await refresh()
}
</script>

<template>
  <USlideover>
    <div class="flex flex-col h-full">
      <div class="p-4 border-b">
        <UButton
          icon="i-lucide-plus"
          label="Nuevo Chat"
          block
          @click="createNewChat"
        />
      </div>

      <div class="flex-1 overflow-y-auto">
        <UNavigationMenu :items="chats?.map(chat => ({
          label: chat.title || 'Nuevo Chat',
          to: `/chat/${chat.id}`,
          icon: 'i-lucide-message-square',
          badge: chat.messageCount
        })) || []" />
      </div>
    </div>
  </USlideover>
</template>
```

### 5.4 Model Selector

Create `app/components/ModelSelector.vue`:

```vue
<script setup lang="ts">
const model = useCookie('selected-model', { default: () => 'google/gemini-2.5-flash-preview-05-20' })

const models = [
  { label: 'Gemini 2.5 Flash', value: 'google/gemini-2.5-flash-preview-05-20', icon: 'i-simple-icons-google' },
  { label: 'Claude 3.5 Sonnet', value: 'anthropic/claude-3.5-sonnet', icon: 'i-simple-icons-anthropic' },
  { label: 'GPT-4o Mini', value: 'openai/gpt-4o-mini', icon: 'i-simple-icons-openai' },
  { label: 'Llama 3.3 70B', value: 'meta-llama/llama-3.3-70b-instruct:free', icon: 'i-simple-icons-meta' }
]
</script>

<template>
  <USelectMenu
    v-model="model"
    :items="models"
    value-key="value"
    class="w-48"
  >
    <template #leading>
      <UIcon :name="models.find(m => m.value === model)?.icon" />
    </template>
  </USelectMenu>
</template>
```

### 5.5 Tool Toggles Migration

Create `app/components/ToolToggles.vue`:

```vue
<script setup lang="ts">
const tools = ref([
  { id: 'search_orders', label: 'Buscar órdenes', enabled: true },
  { id: 'get_order_results', label: 'Obtener resultados', enabled: true },
  { id: 'get_order_info', label: 'Info de orden', enabled: true },
  { id: 'edit_results', label: 'Editar resultados', enabled: true },
  { id: 'edit_order_exams', label: 'Editar exámenes', enabled: true },
  { id: 'create_new_order', label: 'Crear orden', enabled: true },
  { id: 'get_available_exams', label: 'Exámenes disponibles', enabled: true },
  { id: 'ask_user', label: 'Preguntar al usuario', enabled: true }
])

const enabledTools = computed(() =>
  tools.value.filter(t => t.enabled).map(t => t.id)
)

defineExpose({ enabledTools })
</script>

<template>
  <div class="space-y-2">
    <h3 class="font-medium text-sm">Herramientas del Lab</h3>
    <div v-for="tool in tools" :key="tool.id" class="flex items-center gap-2">
      <USwitch v-model="tool.enabled" :label="tool.label" />
    </div>
  </div>
</template>
```

### 5.6 🆕 Tool Display in Chat UI

The backend already sends tool calls in the stream. Create custom tool components:

Create `app/components/tool/LabTool.vue`:

```vue
<script setup lang="ts">
defineProps<{
  name: string
  args: Record<string, unknown>
  result?: string
  status: 'pending' | 'running' | 'completed' | 'error'
}>()

// Map tool names to display names and icons
const toolInfo: Record<string, { label: string; icon: string }> = {
  search_orders: { label: 'Buscando órdenes', icon: 'i-lucide-search' },
  get_order_results: { label: 'Obteniendo resultados', icon: 'i-lucide-file-text' },
  get_order_info: { label: 'Info de orden', icon: 'i-lucide-info' },
  edit_results: { label: 'Editando resultados', icon: 'i-lucide-edit' },
  edit_order_exams: { label: 'Editando exámenes', icon: 'i-lucide-list-checks' },
  create_new_order: { label: 'Creando orden', icon: 'i-lucide-plus-circle' },
  get_available_exams: { label: 'Exámenes disponibles', icon: 'i-lucide-list' },
  ask_user: { label: 'Preguntando al usuario', icon: 'i-lucide-message-circle' }
}
</script>

<template>
  <div class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 my-2">
    <div class="flex-shrink-0">
      <UIcon
        :name="status === 'running' ? 'i-lucide-loader-2' : (toolInfo[name]?.icon || 'i-lucide-wrench')"
        :class="{ 'animate-spin': status === 'running' }"
        class="w-5 h-5 text-primary"
      />
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <span class="font-medium text-sm">
          {{ toolInfo[name]?.label || name }}
        </span>
        <UBadge
          :color="status === 'completed' ? 'success' : status === 'error' ? 'error' : 'info'"
          size="xs"
        >
          {{ status === 'running' ? 'Ejecutando...' : status === 'completed' ? '✓' : status }}
        </UBadge>
      </div>

      <!-- Show tool arguments -->
      <div v-if="Object.keys(args).length > 0" class="mt-1 text-xs text-gray-500 dark:text-gray-400">
        <div v-for="(value, key) in args" :key="key" class="truncate">
          <span class="font-mono">{{ key }}:</span>
          <span v-if="Array.isArray(value)">{{ value.join(', ') }}</span>
          <span v-else>{{ String(value).slice(0, 50) }}{{ String(value).length > 50 ? '...' : '' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
```

Then integrate in `chat/[id].vue`:

```vue
<UChatMessages :messages="messages" :status="status">
  <template #message="{ message }">
    <!-- Handle tool invocation parts -->
    <template v-for="(part, index) in message.parts" :key="index">
      <ToolLabTool
        v-if="part.type === 'tool-invocation'"
        :name="part.toolName"
        :args="part.args"
        :result="part.result"
        :status="part.state"
      />

      <!-- Handle text parts with MDC -->
      <MDC v-else-if="part.type === 'text'" :value="part.text" />

      <!-- Handle reasoning parts -->
      <Reasoning v-else-if="part.type === 'reasoning'" :text="part.text" />
    </template>
  </template>
</UChatMessages>
```

---

## Phase 6: Special Features Migration

### 6.1 Multimodal Support (Images, Audio, Files)

The current implementation supports:
- Image upload/paste/camera
- Audio recording
- File attachments (PDF, etc.)

Create `app/composables/useMultimodal.ts`:

```typescript
export function useMultimodal() {
  const files = ref<File[]>([])

  async function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement
    if (input.files) {
      files.value = [...files.value, ...Array.from(input.files)]
    }
  }

  async function handlePaste(event: ClipboardEvent) {
    const items = event.clipboardData?.items
    if (!items) return

    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) files.value.push(file)
      }
    }
  }

  async function captureFromCamera() {
    // Implementation for mobile camera capture
  }

  async function recordAudio() {
    // Implementation for audio recording
  }

  function convertToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as string)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  return {
    files,
    handleFileSelect,
    handlePaste,
    captureFromCamera,
    recordAudio,
    convertToBase64
  }
}
```

### 6.2 PWA Support (Optional)

Add `@vite-pwa/nuxt` for PWA capabilities:

```bash
pnpm add -D @vite-pwa/nuxt
```

Update `nuxt.config.ts`:

```typescript
export default defineNuxtConfig({
  modules: ['@nuxt/ui', 'nuxt-auth-utils', '@vite-pwa/nuxt'],
  pwa: {
    manifest: {
      name: 'Lab Assistant',
      short_name: 'Lab AI',
      theme_color: '#ffffff'
    }
  }
})
```

---

## Phase 7: Migration Steps (Execution Order)

### Step 1: Setup (Day 1)
- [ ] Create new Nuxt project from template
- [ ] Install all dependencies
- [ ] Configure environment variables
- [ ] Setup database schema

### Step 2: Core Backend (Day 2)
- [ ] Implement database operations (CRUD)
- [ ] Create API routes for chats
- [ ] Implement chat streaming endpoint
- [ ] Connect to Python backend

### Step 3: Authentication (Day 3)
- [ ] Setup nuxt-auth-utils
- [ ] Implement Google OAuth handler
- [ ] Add authentication middleware
- [ ] Create login page

### Step 4: Core UI (Day 4-5)
- [ ] Implement main chat page with UChatMessages/UChatPrompt
- [ ] Create chat sidebar with history
- [ ] Add model selector
- [ ] Add tool toggles

### Step 5: Advanced Features (Day 6-7)
- [ ] Implement multimodal support (images, audio, files)
- [ ] Add file viewer/lightbox
- [ ] Implement command palette
- [ ] Add keyboard shortcuts

### Step 6: Testing & Polish (Day 8)
- [ ] Test all chat functionality
- [ ] Verify database persistence
- [ ] Test streaming responses
- [ ] Mobile responsive testing

### Step 7: Data Migration (Day 9)
- [ ] Create migration script for existing data
- [ ] Backup current database
- [ ] Run migration
- [ ] Verify data integrity

### Step 8: Deployment (Day 10)
- [ ] Setup production database (Turso)
- [ ] Configure production environment
- [ ] Deploy to hosting platform
- [ ] Final testing

---

## Key Files to Migrate

### From Current → To New

| Current File | Purpose | New Location |
|-------------|---------|--------------|
| `src/components/chat.tsx` | Main chat UI | `app/pages/chat/[id].vue` |
| `src/app/api/chat/route.ts` | Chat API | `server/api/chats/[id].post.ts` |
| `src/lib/db/index.ts` | DB operations | `server/utils/db.ts` |
| `src/lib/db/schema.ts` | DB schema | `server/database/schema.ts` |
| `src/auth.ts` | Auth config | `server/routes/auth/google.get.ts` |
| `src/components/chat-sidebar.tsx` | Chat list | `app/components/ChatSidebar.vue` |
| `src/components/model-selector.tsx` | Model picker | `app/components/ModelSelector.vue` |
| `src/components/tool-toggles.tsx` | Tool toggles | `app/components/ToolToggles.vue` |
| `src/lib/models.ts` | Model configs | `app/utils/models.ts` |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Data loss during migration | Full backup before migration, migration script with verification |
| AI SDK v6 → v5 breaking changes | Test thoroughly, refer to AI SDK migration guide |
| Authentication changes | Keep Google OAuth, just use different library |
| Backend integration issues | Backend API remains same, only frontend changes |
| Feature parity gaps | Prioritize core chat functionality first |

---

## Post-Migration Cleanup

1. Archive old `frontend/` directory (rename to `frontend-nextjs-archive/`)
2. Rename `frontend-nuxt/` to `frontend/`
3. Update any deployment scripts
4. Update documentation
5. Remove old dependencies from root package.json if any

---

## Resources

- [Nuxt AI Chatbot Template](https://github.com/nuxt-ui-templates/chat)
- [Nuxt UI Documentation](https://ui.nuxt.com)
- [AI SDK Vue Documentation](https://sdk.vercel.ai/docs/ai-sdk-ui/overview)
- [nuxt-auth-utils Documentation](https://github.com/atinux/nuxt-auth-utils)
- [Drizzle ORM Documentation](https://orm.drizzle.team)
- [Tutorial: Build an AI Chatbot with Nuxt](https://ui.nuxt.com/blog/how-to-build-an-ai-chat)
