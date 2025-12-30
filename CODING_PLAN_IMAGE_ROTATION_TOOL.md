# Coding Plan: Image Rotation Tool with Visual Feedback

## Overview

This document describes the implementation of an image rotation pre-processing feature that:
1. Shows image rotation as a "tool" executing in the chat UI
2. Displays miniature thumbnails of rotated images after completion (when rotation != 0)
3. Makes thumbnails clickable for larger view
4. Replaces original images with rotated versions before sending to Gemini

Also includes: Remove nuxt devtools.

---

## Research Summary: AI SDK Capabilities

### AI SDK Stream Protocol (v1)

The AI SDK uses Server-Sent Events (SSE) with specific event types. Key findings:

**Header Required:**
```
x-vercel-ai-ui-message-stream: v1
```

**Tool Events (can be emitted synthetically):**
```json
// Start tool execution
{"type": "tool-input-start", "toolCallId": "call_xxx", "toolName": "image-rotation"}

// Tool input available (shows arguments)
{"type": "tool-input-available", "toolCallId": "call_xxx", "toolName": "image-rotation", "input": {...}}

// Tool output available (shows result)
{"type": "tool-output-available", "toolCallId": "call_xxx", "output": {...}}
```

**File Parts (for showing images in stream):**
```json
{"type": "file", "url": "data:image/jpeg;base64,...", "mediaType": "image/jpeg"}
```

**Stream Termination:**
```
data: [DONE]
```

### Key Insight

The frontend (AI SDK Vue) renders tools based on SSE events, **not** based on whether the LLM called them. This means we can emit **synthetic tool events** from our server to show pre-processing steps as tools.

### Sources
- [AI SDK Stream Protocol](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol)
- [AI SDK 4.2 - Message Parts](https://vercel.com/blog/ai-sdk-4-2)
- [AI SDK 6 - Agents](https://vercel.com/blog/ai-sdk-6)

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ Frontend (Nuxt/Vue)                                                 │
│                                                                     │
│  ┌──────────────────┐     ┌─────────────────────┐                  │
│  │ useFileUpload.ts │────▶│ useImageRotation.ts │                  │
│  │ (adds files)     │     │ (background detect) │                  │
│  └────────┬─────────┘     └─────────────────────┘                  │
│           │                                                         │
│           ▼                                                         │
│  ┌──────────────────┐                                               │
│  │ Chat sendMessage │                                               │
│  │ (with files)     │                                               │
│  └────────┬─────────┘                                               │
└───────────┼─────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│ Nuxt Server Route: /api/chats/[id].post.ts                        │
│                                                                    │
│  - Receives messages with image parts                              │
│  - Currently just proxies to backend                               │
│  - TODO: Emit rotation tool events here                           │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────────────┐
│ Python Backend: /api/chat/aisdk                                   │
│                                                                    │
│  - StreamAdapter emits AI SDK protocol events                     │
│  - LangGraph agent with tools                                     │
│  - Gemini/OpenRouter for AI                                       │
└───────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Task 0: Remove Nuxt DevTools

**File:** `frontend-nuxt/nuxt.config.ts`

**Change:**
```typescript
// Before
devtools: {
  enabled: true
}

// After
devtools: {
  enabled: false
}
```

---

### Task 1: Modify Frontend to Track Rotation State

**File:** `frontend-nuxt/app/composables/useFileUpload.ts`

**Changes:**
1. Track which images have pending rotation
2. Expose a method to wait for all pending rotations
3. Include rotation status in the file data sent to backend

**New exported values:**
```typescript
export function useFileUploadWithStatus(_chatId: string) {
  // ... existing code ...

  // NEW: Check if any images are still processing rotation
  const hasPendingRotations = computed(() =>
    files.value.some(f =>
      f.file.type.startsWith('image/') &&
      f.status === 'uploaded' &&
      f.rotation === undefined  // Not yet processed
    )
  )

  // NEW: Wait for all rotation detections to complete
  async function waitForRotations(): Promise<void> {
    // Implementation uses useImageRotation's pending promises
  }

  return {
    // ... existing ...
    hasPendingRotations,
    waitForRotations
  }
}
```

---

### Task 2: Modify Chat Page to Handle Rotation Before Send

**File:** `frontend-nuxt/app/pages/chat/[id].vue`

**Current behavior:**
```typescript
async function handleSubmit(e: Event) {
  e.preventDefault()
  if (input.value.trim() && !isRecording.value) {
    chat.sendMessage({
      text: input.value,
      files: uploadedFiles.value.length > 0 ? uploadedFiles.value : undefined
    })
    // ...
  }
}
```

**New behavior:**
```typescript
async function handleSubmit(e: Event) {
  e.preventDefault()
  if (input.value.trim() && !isRecording.value) {
    // Include metadata about pending rotations
    const filesToSend = uploadedFiles.value.map(f => ({
      ...f,
      rotationPending: f.rotation === undefined && f.mediaType.startsWith('image/')
    }))

    chat.sendMessage({
      text: input.value,
      files: filesToSend.length > 0 ? filesToSend : undefined
    })
    // ...
  }
}
```

---

### Task 3: Create Stream Adapter for Nuxt Server

**File:** `frontend-nuxt/server/utils/streamAdapter.ts` (NEW)

Creates a TypeScript version of the stream adapter for Nuxt to emit synthetic events:

```typescript
import { randomUUID } from 'crypto'

export class NuxtStreamAdapter {
  private messageId: string
  private textId: string | null = null

  constructor() {
    this.messageId = `msg_${randomUUID().slice(0, 12)}`
  }

  private sse(data: unknown): string {
    return `data: ${JSON.stringify(data)}\n\n`
  }

  startMessage(): string {
    return this.sse({ type: 'start', messageId: this.messageId })
  }

  toolStart(toolCallId: string, toolName: string): string {
    return this.sse({
      type: 'tool-input-start',
      toolCallId,
      toolName
    })
  }

  toolInputAvailable(toolCallId: string, toolName: string, input: Record<string, unknown>): string {
    return this.sse({
      type: 'tool-input-available',
      toolCallId,
      toolName,
      input
    })
  }

  toolOutputAvailable(toolCallId: string, output: unknown): string {
    return this.sse({
      type: 'tool-output-available',
      toolCallId,
      output
    })
  }

  filePart(url: string, mediaType: string): string {
    return this.sse({
      type: 'file',
      url,
      mediaType
    })
  }

  finish(): string {
    return this.sse({ type: 'finish', finishReason: 'stop' }) + 'data: [DONE]\n\n'
  }
}
```

---

### Task 4: Modify Nuxt API Route for Image Rotation

**File:** `frontend-nuxt/server/api/chats/[id].post.ts`

This is the core change. The route needs to:
1. Detect images in the message that need rotation
2. Process rotation (call detect-rotation endpoint if not done)
3. Emit synthetic tool events
4. If rotation applied, emit file parts for rotated images
5. Replace original images with rotated versions
6. Forward to backend

**Implementation approach:**

```typescript
export default defineEventHandler(async (event) => {
  // ... existing validation ...

  const lastMessage = messages[messages.length - 1]

  // Check for images needing rotation processing
  const imageParts = lastMessage?.parts?.filter(
    (p: any) => p.type === 'file' && p.mediaType?.startsWith('image/')
  ) || []

  // If we have images, handle rotation as a tool
  if (imageParts.length > 0) {
    // Create a streaming response that:
    // 1. Emits tool-start for image-rotation
    // 2. Processes each image
    // 3. Emits tool-output with rotation results
    // 4. Emits file parts for rotated images
    // 5. Then continues with the backend stream

    return createRotationAwareStream(event, messages, imageParts, /* other params */)
  }

  // No images - proceed normally
  return proxyToBackend(event, messages, /* other params */)
})

async function createRotationAwareStream(event, messages, imageParts, ...) {
  const adapter = new NuxtStreamAdapter()
  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    async start(controller) {
      // Emit message start
      controller.enqueue(encoder.encode(adapter.startMessage()))

      // Emit tool start
      const toolCallId = `call_rotation_${Date.now()}`
      controller.enqueue(encoder.encode(adapter.toolStart(toolCallId, 'image-rotation')))
      controller.enqueue(encoder.encode(adapter.toolInputAvailable(toolCallId, 'image-rotation', {
        images: imageParts.map(p => p.name || 'image')
      })))

      // Process each image for rotation
      const rotationResults = []
      for (const imagePart of imageParts) {
        if (!imagePart.rotatedBase64 && imagePart.data) {
          // Call rotation detection
          const result = await detectRotation(imagePart.data, imagePart.mediaType)
          rotationResults.push({
            name: imagePart.name,
            rotation: result.rotation,
            applied: result.rotation !== 0,
            rotatedData: result.rotatedBase64
          })

          // Replace image data if rotated
          if (result.rotation !== 0 && result.rotatedBase64) {
            imagePart.data = result.rotatedBase64
            imagePart.url = `data:${imagePart.mediaType};base64,${result.rotatedBase64}`
          }
        } else if (imagePart.rotatedBase64) {
          // Already rotated by frontend
          rotationResults.push({
            name: imagePart.name,
            rotation: imagePart.rotation || 0,
            applied: (imagePart.rotation || 0) !== 0
          })
        }
      }

      // Emit tool output
      controller.enqueue(encoder.encode(adapter.toolOutputAvailable(toolCallId, {
        processed: rotationResults.length,
        rotated: rotationResults.filter(r => r.applied).length,
        results: rotationResults
      })))

      // Emit file parts for rotated images (miniatures in chat)
      for (const result of rotationResults) {
        if (result.applied) {
          const imagePart = imageParts.find(p => p.name === result.name)
          if (imagePart) {
            controller.enqueue(encoder.encode(adapter.filePart(
              imagePart.url,
              imagePart.mediaType
            )))
          }
        }
      }

      // Now forward to backend and pipe its stream
      const backendResponse = await fetch(`${backendUrl}/api/chat/aisdk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: convertMessagesForBackend(messages),
          chatId,
          model,
          tools: enabledTools
        })
      })

      if (!backendResponse.ok || !backendResponse.body) {
        controller.enqueue(encoder.encode(adapter.finish()))
        controller.close()
        return
      }

      // Pipe backend stream (skip its "start" event since we already sent one)
      const reader = backendResponse.body.getReader()
      let skipStart = true

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        // Filter out duplicate "start" events
        const text = new TextDecoder().decode(value)
        if (skipStart && text.includes('"type":"start"')) {
          skipStart = false
          // Remove the start event line and continue
          const filtered = text.split('\n').filter(line =>
            !line.includes('"type":"start"')
          ).join('\n')
          if (filtered.trim()) {
            controller.enqueue(encoder.encode(filtered))
          }
          continue
        }

        controller.enqueue(value)
      }

      controller.close()
    }
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'x-vercel-ai-ui-message-stream': 'v1',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    }
  })
}
```

---

### Task 5: Add Image Rotation Tool to LabTool Component

**File:** `frontend-nuxt/app/components/tool/LabTool.vue`

**Add to toolInfo:**
```typescript
const toolInfo: Record<string, { label: string; icon: string; activeLabel: string }> = {
  // ... existing tools ...

  'image-rotation': {
    label: 'Corrección de orientación',
    activeLabel: 'Corrigiendo orientación de imágenes...',
    icon: 'i-lucide-rotate-cw'
  }
}
```

---

### Task 6: Handle File Parts After Tool in Chat Template

**File:** `frontend-nuxt/app/pages/chat/[id].vue`

The `groupMessageParts` function already handles file parts. However, we need to ensure file parts that come after tool results are displayed correctly.

**Current code already handles this:**
```vue
<FileAvatar
  v-else-if="part.type === 'file'"
  :name="getFileName((part as any).url)"
  :type="(part as any).mediaType"
  :preview-url="(part as any).url"
/>
```

The FileAvatar component already:
- Shows image thumbnails
- Has click-to-enlarge via ImageLightbox
- Supports rotation display

**No changes needed** - the existing components will handle the file parts correctly.

---

### Task 7: Create Rotation Detection Utility for Server

**File:** `frontend-nuxt/server/utils/imageRotation.ts` (NEW)

Moves rotation logic to a reusable server utility:

```typescript
import { $fetch } from 'ofetch'

interface RotationResult {
  rotation: number
  detected: boolean
  rotatedBase64?: string
}

export async function detectAndRotateImage(
  base64Data: string,
  mimeType: string
): Promise<RotationResult> {
  try {
    // Call our existing rotation detection endpoint
    const result = await $fetch<{ rotation: number; detected: boolean }>('/api/detect-rotation', {
      method: 'POST',
      body: { imageBase64: base64Data, mimeType }
    })

    if (result.rotation === 0) {
      return { rotation: 0, detected: result.detected }
    }

    // Apply rotation on server (using canvas in a worker or sharp library)
    const rotatedBase64 = await rotateImageServer(base64Data, mimeType, result.rotation)

    return {
      rotation: result.rotation,
      detected: result.detected,
      rotatedBase64
    }
  } catch (error) {
    console.error('[imageRotation] Error:', error)
    return { rotation: 0, detected: false }
  }
}

async function rotateImageServer(base64: string, mimeType: string, degrees: number): Promise<string> {
  // Option 1: Use sharp library (recommended for server)
  // Option 2: Return original and let frontend handle rotation display
  // For now, we'll use the frontend's rotated data if available

  // This is a placeholder - actual implementation depends on server capabilities
  return base64
}
```

**Note:** Server-side image rotation can use the `sharp` library. Add to package.json:
```json
"dependencies": {
  "sharp": "^0.33.0"
}
```

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `nuxt.config.ts` | MODIFY | Set `devtools.enabled: false` |
| `server/utils/streamAdapter.ts` | CREATE | Nuxt stream adapter for AI SDK protocol |
| `server/utils/imageRotation.ts` | CREATE | Server-side rotation detection utility |
| `server/api/chats/[id].post.ts` | MODIFY | Add rotation tool emission before backend proxy |
| `app/components/tool/LabTool.vue` | MODIFY | Add image-rotation tool info |
| `app/composables/useFileUpload.ts` | MODIFY | Track rotation pending state |
| `app/composables/useImageRotation.ts` | MODIFY | Add method to wait for pending rotations |
| `package.json` | MODIFY | Add `sharp` dependency for server rotation |

---

## Testing Checklist

1. **Rotation Detection Flow:**
   - [ ] Paste an image that is rotated 90 degrees
   - [ ] Submit the message
   - [ ] Verify "image-rotation" tool shows as executing
   - [ ] Verify tool completes with rotation info
   - [ ] Verify rotated image thumbnail appears after tool
   - [ ] Click thumbnail to see full-size rotated image

2. **No Rotation Needed:**
   - [ ] Paste a correctly oriented image
   - [ ] Submit the message
   - [ ] Verify tool shows but indicates 0 rotation
   - [ ] No file part emitted (since no rotation applied)

3. **Multiple Images:**
   - [ ] Paste 3 images (1 rotated, 2 correct)
   - [ ] Verify tool processes all 3
   - [ ] Verify only the rotated image shows as thumbnail

4. **Already Rotated (Frontend):**
   - [ ] Image rotation completes before user sends
   - [ ] Submit message
   - [ ] Tool should show as already completed (fast)

5. **Gemini Receives Correct Image:**
   - [ ] After rotation, AI should describe correctly oriented image
   - [ ] Check backend logs for correct image data

---

## Architecture Diagram (After Implementation)

```
User pastes rotated image
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│ Frontend: useFileUpload                                 │
│   - Converts to base64                                  │
│   - Triggers background rotation detection              │
│   - May complete before user sends                      │
└───────────────────────┬─────────────────────────────────┘
                        │
User clicks "Send"      │
        │               │
        ▼               ▼
┌─────────────────────────────────────────────────────────┐
│ Nuxt Server: /api/chats/[id].post.ts                   │
│                                                         │
│   1. Check for images in message                        │
│   2. START STREAM with adapter.startMessage()           │
│   3. Emit tool-input-start (image-rotation)             │
│   4. Emit tool-input-available (show images)            │
│   5. For each image:                                    │
│      - If not rotated: call /api/detect-rotation        │
│      - Apply rotation if needed                         │
│   6. Emit tool-output-available (results)               │
│   7. For rotated images: emit file parts                │
│   8. Replace images in message with rotated versions    │
│   9. Proxy remaining stream from backend                │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ Python Backend                                          │
│   - Receives message with CORRECTLY ROTATED images      │
│   - Sends to Gemini                                     │
│   - Streams response                                    │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ Frontend: Chat UI                                       │
│                                                         │
│   ┌─────────────────────────────────────┐               │
│   │ 🔄 Corrección de orientación        │               │
│   │    images: ["photo1.jpg"]           │               │
│   │    ✓ Completado                     │               │
│   │    Resultado: 1 imagen rotada 90°   │               │
│   └─────────────────────────────────────┘               │
│                                                         │
│   ┌──────────┐  ◄── Clickable thumbnail                │
│   │ 📷       │      Opens ImageLightbox                │
│   │ (90°)    │      with correct rotation              │
│   └──────────┘                                          │
│                                                         │
│   💬 AI Response about the image...                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Order

1. **Task 0:** Remove nuxt devtools (5 min)
2. **Task 3:** Create stream adapter utility (15 min)
3. **Task 5:** Add tool info to LabTool (5 min)
4. **Task 4:** Modify API route - main implementation (45 min)
5. **Task 1 & 2:** Frontend tracking changes if needed (15 min)
6. **Testing:** Full flow testing (20 min)

**Total estimated effort:** ~2 hours

---

## Dependencies

- `sharp` (optional, for server-side image rotation)
- Existing: `@openrouter/ai-sdk-provider` (already used for rotation detection)

---

## Rollback Plan

If issues arise:
1. The existing rotation detection in the frontend still works
2. The backend proxy can be restored to pass-through mode
3. Tool display is purely visual - not critical to functionality
