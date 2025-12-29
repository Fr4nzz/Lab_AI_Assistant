# Current Implementation Documentation

## Overview

This document describes the current implementation of the Lab AI Assistant chat interface, focusing on the features that are not working correctly:

1. **Image Rotation Tool Display** - Rotation detection happens but tool is not shown in UI
2. **Chat Title Generation** - New chats remain "Nuevo Chat" instead of getting auto-generated titles

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (Nuxt 3)                            │
├─────────────────────────────────────────────────────────────────────┤
│  chat/[id].vue                                                      │
│  ├── Uses @ai-sdk/vue Chat class                                    │
│  ├── Uses DefaultChatTransport from 'ai'                            │
│  ├── Custom handleSubmit() for form submission                      │
│  └── pendingRotationResults ref for passing rotation data           │
│                                                                     │
│  useFileUpload.ts (composable)                                      │
│  ├── Manages file uploads and rotation detection                    │
│  ├── rotationResults Map<fileId, FileRotationState>                 │
│  ├── hasPendingRotations computed                                   │
│  └── waitForRotations() promise                                     │
├─────────────────────────────────────────────────────────────────────┤
│  server/api/chats/[id].post.ts (Nuxt API Route)                     │
│  ├── Receives messages + rotationResults from frontend              │
│  ├── Proxies to Python backend                                      │
│  ├── Triggers generateTitle() for new chats                         │
│  └── Uses OpenRouter free models for title generation               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Backend (Python FastAPI)                        │
├─────────────────────────────────────────────────────────────────────┤
│  server.py                                                          │
│  ├── /api/chat/aisdk - Main chat endpoint (AI SDK stream format)    │
│  ├── /api/detect-rotation - Image rotation detection                │
│  └── StreamAdapter - Converts LangGraph to AI SDK stream format     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Feature 1: Image Rotation Tool Display

### Current Flow (NOT WORKING)

```
1. User pastes image
   └── addFiles() called in useFileUpload.ts
       └── Sets rotationResults[fileId] = { state: 'pending' }
       └── Calls processImageRotation() async (fire-and-forget)

2. processImageRotation() runs
   └── Calls /api/detect-rotation
   └── On completion: Sets rotationResults[fileId] = { state: 'completed', rotation: N }

3. User clicks submit
   └── handleSubmit() called (SHOULD log "[handleSubmit] Called with:")
   └── Checks hasPendingRotations
       ├── If true: waitForRotations() then sendMessage
       └── If false: capture currentRotationResults, sendMessage
   └── Sets pendingRotationResults.value = [...]
   └── chat.sendMessage() called

4. Transport body() function called
   └── Returns { rotationResults: pendingRotationResults.value }

5. Nuxt API receives request
   └── Should log rotationResults received
   └── Forwards to Python backend

6. Python backend
   └── If rotationResults present: streams rotation tool calls
   └── Then processes main AI response
```

### Current Code Locations

| File | Purpose |
|------|---------|
| `app/pages/chat/[id].vue:75-111` | Chat class initialization with transport |
| `app/pages/chat/[id].vue:122-206` | handleSubmit function |
| `app/pages/chat/[id].vue:48-56` | pendingRotationResults ref |
| `app/composables/useFileUpload.ts:246-258` | hasPendingRotations computed |
| `app/composables/useFileUpload.ts:260-332` | waitForRotations function |
| `server/api/chats/[id].post.ts:183-199` | Receives rotationResults |
| `backend/server.py:1135-1165` | Streams rotation as tool calls |

### Known Issues

1. **`[handleSubmit]` log not appearing in browser console**
   - This is critical - if handleSubmit isn't called, nothing works
   - UChatPrompt @submit may not be triggering our handler

2. **Timing issue with pendingRotationResults**
   - The `body()` function is called when request is made
   - `pendingRotationResults.value` may not be set when body() runs

3. **Vue reactivity issue**
   - `currentRotationResults` depends on `files.value`
   - If files are cleared before we read results, we get nothing

### Research Needed for AI SDK

- [ ] How does `@ai-sdk/vue` Chat class handle form submission?
- [ ] What is the correct way to use UChatPrompt with custom submit handling?
- [ ] Does DefaultChatTransport body() get called synchronously with sendMessage()?
- [ ] What is the proper way to pass extra data with messages?
- [ ] How do tool calls appear in UIMessage.parts?

---

## Feature 2: Chat Title Generation

### Current Flow (NOT WORKING)

```
1. User sends first message to new chat
   └── POST /api/chats/[id]

2. Nuxt API route handles request
   └── Checks if lastMessage.role === 'user'
   └── Checks isDuplicate (compares with lastDbMessage)
   └── If not duplicate:
       └── Saves message to DB
       └── Checks needsTitle (chat.title === 'Nuevo Chat' or empty)
       └── If needsTitle: calls generateTitle()

3. generateTitle() function
   └── Uses OpenRouter free models with provider.sort: 'latency'
   └── Generates title from message content
   └── Updates chat in database
```

### Current Code Locations

| File | Purpose |
|------|---------|
| `server/api/chats/[id].post.ts:32-117` | generateTitle function |
| `server/api/chats/[id].post.ts:214-248` | Title generation trigger logic |
| `server/utils/openrouter-models.ts` | Free models fetching |

### Known Issues

1. **No logs appearing for title generation**
   - `[API/chat] Chat title check` log not showing
   - Either code path not reached or logs not being output

2. **OPENROUTER_API_KEY may not be set**
   - Required in frontend-nuxt/.env
   - Without it, title generation is skipped silently

3. **isDuplicate check may be preventing title generation**
   - If message is detected as duplicate, entire block is skipped

### Research Needed for AI SDK

- [ ] Is there a built-in way to handle chat titles in AI SDK?
- [ ] What's the proper pattern for side-effects (like title gen) in stream handlers?

---

## Key Questions to Research

### AI SDK Core Concepts

1. **Chat class from @ai-sdk/vue**
   - Constructor options and their behavior
   - sendMessage() method signature and behavior
   - How it interacts with transport
   - When is body() called relative to sendMessage()?

2. **DefaultChatTransport**
   - How body() function works
   - When is it invoked?
   - Is it synchronous with sendMessage()?

3. **UChatPrompt component (Nuxt UI)**
   - How @submit event works
   - Does it have its own submission logic?
   - How to properly integrate with AI SDK Chat

4. **UIMessage structure**
   - What are the possible part types?
   - How are tool calls represented in parts?
   - How does streaming affect parts?

5. **Stream Protocol**
   - What events create tool parts?
   - How to stream custom tool calls from backend?
   - What is the exact format for tool-input-start, tool-output-available?

### Nuxt UI Specific

1. **UChatPrompt**
   - Source code or documentation
   - How submission works internally
   - How to intercept/customize submission

2. **UChatMessages**
   - How it renders message parts
   - What part types it understands

---

## Files to Review

```
Frontend:
- node_modules/@ai-sdk/vue/dist/index.d.ts (Chat class types)
- node_modules/ai/dist/index.d.ts (DefaultChatTransport types)
- @nuxt/ui components source (if available)

Documentation:
- https://sdk.vercel.ai/docs/ai-sdk-ui
- https://sdk.vercel.ai/docs/ai-sdk-ui/chatbot
- https://sdk.vercel.ai/docs/ai-sdk-ui/stream-protocol
- https://ui.nuxt.com/components/chat-prompt (Nuxt UI docs)
```

---

## Next Steps

1. Research AI SDK documentation thoroughly
2. Understand the exact flow of Chat.sendMessage() → transport.body() → request
3. Determine if UChatPrompt has its own submit behavior
4. Create clean implementation based on documented patterns
