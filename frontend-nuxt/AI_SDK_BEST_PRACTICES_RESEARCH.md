# AI SDK Best Practices Research

## Date: 2025-12-30

## Issues Identified

### Issue 1: Rotated Image Thumbnail Not Displayed

**Symptoms:**
- Server detects 270° rotation needed
- Log shows: `[imageRotation] Server detected 270deg for pasted-image-... (cannot apply server-side)`
- `[API/chat] Proxying to backend with 0 rotated images`
- No thumbnail appears after the rotation tool

**Root Cause Analysis:**

1. **Async Detection Race Condition**: The frontend's `detectRotation` runs asynchronously via `/api/detect-rotation`. When the user sends a message BEFORE detection completes:
   - `hasRotatedBase64: false` (no rotated data yet)
   - `rotation: undefined` (detection not complete)
   - `rotationPending: true`

2. **No Server-Side Rotation Capability**: The server can detect rotation using OpenRouter vision models but cannot APPLY rotation because there's no image manipulation library (like `sharp`) installed.

3. **File Part Emission Condition**: In `[id].post.ts:345-357`, we only emit file parts when:
   ```typescript
   if (result && result.applied && result.originalRotation !== 0)
   ```
   But `result.applied` is always `false` when server-side rotation is unavailable.

4. **Missing `filename` Property**: According to AI SDK docs, `FileUIPart` expects:
   ```typescript
   { type: 'file', url: string, mediaType: string, filename?: string }
   ```
   We're missing `filename` which may affect thumbnail rendering.

**AI SDK Best Practice Reference:**
- [Stream Protocol](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol): File parts should have `url` and `mediaType`
- [Message Component](https://ai-sdk.dev/elements/components/message): Images display as 96x96 thumbnails

---

### Issue 2: Tool Result Shows "Ver respuesta del asistente"

**Symptoms:**
- Image rotation tool completes with result: `{ processed: 1, rotated: 0, detected: 1, results: [...] }`
- UI shows: "Resultado: Ver respuesta del asistente"

**Root Cause:**
In `LabTool.vue:122-125`:
```vue
<span class="ml-1">
  {{ typeof result === 'string' ? result.slice(0, 100) : 'Ver respuesta del asistente' }}
</span>
```
This only handles string results. Object results fall through to the default message.

**AI SDK Best Practice Reference:**
- [Tool Component](https://ai-sdk.dev/elements/components/tool): "Shows a completed tool with successful results... the output is a JSON object, so you can use the CodeBlock component to display it."

---

### Issue 3: Chat Title Not Updating in Sidebar Without Refresh

**Symptoms:**
- Title generation logs: `[API/chat] Generated title: Corrección orientación imagen` (at 9:00:49 PM)
- But user sees the new title only after page refresh
- `refreshNuxtData('chats')` called in `onFinish` but title not yet generated

**Root Cause:**
The title generation is fire-and-forget:
```typescript
// In [id].post.ts:515-517
if (!chat.title || chat.title === 'Nuevo Chat') {
  generateTitle(chatId, textContent).catch(console.error)  // Fire and forget!
}
```

The `onFinish` callback in the Chat instance fires when the STREAM completes, but title generation happens asynchronously:
1. Stream completes → `onFinish` fires → `refreshNuxtData('chats')` called
2. Meanwhile, title generation is still running (free model = slow)
3. Title saved to DB ~1 minute later
4. Sidebar still shows old title because refresh already happened

**AI SDK Best Practice Reference:**
- [Chatbot Persistence](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-message-persistence): Use `onFinish` callback for persistence, but ensure async operations complete

---

### Issue 4: Server-Side Rotation Not Available

**Symptoms:**
- Log: `(cannot apply server-side)`
- Images sent unrotated to Gemini

**Root Cause:**
No image manipulation library installed on server. The `imageRotation.ts` can detect but not apply rotations.

---

## Coding Plan

### Phase 1: Fix Server-Side Image Rotation with `sharp`

**Goal:** Enable server to apply detected rotations before sending to backend.

**Files to modify:**
- `package.json` - Add `sharp` dependency
- `server/utils/imageRotation.ts` - Implement server-side rotation

**Implementation:**

1. Install sharp:
   ```bash
   cd frontend-nuxt && npm install sharp
   ```

2. Update `imageRotation.ts`:
   ```typescript
   import sharp from 'sharp'

   async function applyRotation(base64Data: string, mimeType: string, rotation: number): Promise<string> {
     const buffer = Buffer.from(base64Data, 'base64')
     const rotated = await sharp(buffer)
       .rotate(rotation)
       .toBuffer()
     return rotated.toString('base64')
   }
   ```

3. Update `processImagesForRotation` to apply rotation when detected:
   ```typescript
   // Case 4: Need to detect and apply rotation
   if (detected && rotation !== 0) {
     const rotatedData = await applyRotation(image.data, image.mediaType, rotation)
     results.push({ name: imageName, originalRotation: rotation, applied: true })
     processedImages.push({
       ...image,
       data: rotatedData,
       url: `data:${image.mediaType};base64,${rotatedData}`
     })
   }
   ```

---

### Phase 2: Fix File Part Emission for Thumbnails

**Goal:** Always emit rotated image thumbnails when rotation was detected (regardless of where applied).

**Files to modify:**
- `server/api/chats/[id].post.ts` - Fix file part emission logic and add filename

**Implementation:**

1. Change the condition for emitting file parts:
   ```typescript
   // Emit file parts for any images where rotation was detected
   for (let i = 0; i < results.length; i++) {
     const result = results[i]
     // Show thumbnail whenever rotation was detected (even if not applied)
     if (result && result.originalRotation !== 0) {
       const processedImage = processedImages[i]
       if (processedImage && processedImage.url) {
         controller.enqueue(encoder.encode(adapter.filePart(
           processedImage.url,
           processedImage.mediaType,
           processedImage.name || `rotated-image-${i + 1}`  // Add filename
         )))
         collector.addFile(processedImage.url, processedImage.mediaType)
       }
     }
   }
   ```

2. Update `streamAdapter.ts` to include filename:
   ```typescript
   filePart(url: string, mediaType: string, filename?: string): string {
     return this.sse({
       type: 'file',
       url,
       mediaType,
       filename
     })
   }
   ```

---

### Phase 3: Improve Tool Result Display for image-rotation

**Goal:** Show meaningful rotation details instead of "Ver respuesta del asistente"

**Files to modify:**
- `app/components/tool/LabTool.vue` - Add special handling for image-rotation results

**Implementation:**

Update the result display logic:
```vue
<!-- Show result summary if completed -->
<div v-if="isCompleted && result" class="mt-2 text-xs text-gray-500 dark:text-gray-400">
  <span class="font-medium">Resultado:</span>
  <span class="ml-1">
    <template v-if="name === 'image-rotation' && typeof result === 'object'">
      {{ formatRotationResult(result as any) }}
    </template>
    <template v-else>
      {{ typeof result === 'string' ? result.slice(0, 100) : 'Ver respuesta del asistente' }}
      {{ typeof result === 'string' && result.length > 100 ? '...' : '' }}
    </template>
  </span>
</div>
```

Add helper function:
```typescript
function formatRotationResult(result: { processed?: number; rotated?: number; detected?: number; results?: Array<{ name: string; rotation: number; applied: boolean }> }): string {
  if (!result.results || result.results.length === 0) {
    return 'Sin imágenes procesadas'
  }

  const rotationInfo = result.results.map(r => {
    if (r.rotation === 0) return `${r.name}: sin rotación`
    return `${r.name}: ${r.rotation}° ${r.applied ? '(aplicada)' : '(detectada)'}`
  }).join(', ')

  return rotationInfo
}
```

---

### Phase 4: Fix Chat Title Real-Time Update

**Goal:** Update sidebar when title is generated, without requiring page refresh.

**Option A: Server-Sent Event for Title Update**

**Files to modify:**
- `server/api/chats/[id].post.ts` - Return title in response header or emit as custom data part
- `app/pages/chat/[id].vue` - Watch for title updates

**Implementation (Option A):**

1. Wait for title generation and include in stream:
   ```typescript
   // In createRotationAwareStream, after saving assistant message
   if (!chat.title || chat.title === 'Nuevo Chat') {
     try {
       const title = await generateTitleAndSave(chatId, textContent)
       if (title) {
         // Emit title as custom data part
         controller.enqueue(encoder.encode(adapter.customData('chat-title', { title })))
       }
     } catch (e) {
       console.error('Title generation failed:', e)
     }
   }
   ```

2. Handle title in frontend:
   ```typescript
   // In chat transport or onFinish
   if (data.type === 'chat-title') {
     updateChatTitle(chatId, data.title)
   }
   ```

**Option B: Poll/Watch for Title Changes (Simpler)**

**Files to modify:**
- `app/pages/chat/[id].vue` - Add watcher for title updates

**Implementation (Option B):**

1. Use `useFetch` with `watch` to refresh title periodically:
   ```typescript
   // After onFinish, refresh chat data
   onFinish() {
     // Immediate refresh
     refreshNuxtData('chats')
     // Delayed refresh to catch async title generation
     setTimeout(() => refreshNuxtData('chats'), 3000)
     setTimeout(() => refreshNuxtData('chats'), 10000)
   }
   ```

**Option C: Use WebSocket/EventSource for Real-Time Updates (Best)**

This is the most robust but requires more infrastructure changes.

**Recommended: Option B for simplicity**, then upgrade to Option A/C later.

---

### Phase 5: Ensure Frontend Waits for Rotation Before Send (Optional Enhancement)

**Goal:** Prevent race condition by waiting for frontend rotation detection.

**Files to modify:**
- `app/composables/useFileUpload.ts` - Add method to wait for pending rotations
- `app/pages/chat/[id].vue` - Wait before submitting

**Implementation:**

1. Add waiting mechanism:
   ```typescript
   async function waitForPendingRotations(): Promise<void> {
     const pending = Array.from(pendingRotations.value.values())
     if (pending.length > 0) {
       await Promise.all(pending)
     }
   }
   ```

2. Update submit handler:
   ```typescript
   async function handleSubmit(e: Event) {
     e.preventDefault()
     if (input.value.trim() && !isRecording.value) {
       // Wait for any pending rotations
       await waitForPendingRotations()

       chat.sendMessage({
         text: input.value,
         files: uploadedFiles.value.length > 0 ? uploadedFiles.value : undefined
       })
       // ...
     }
   }
   ```

---

## Execution Order

1. **Phase 1** - Install `sharp` and implement server-side rotation (most impactful fix)
2. **Phase 2** - Fix file part emission to show thumbnails
3. **Phase 3** - Improve tool result display
4. **Phase 4** - Fix title updates (Option B first)
5. **Phase 5** - Optional: Wait for frontend rotation

---

## Sources

- [AI SDK UI: Stream Protocol](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol)
- [AI SDK UI: createUIMessageStream](https://ai-sdk.dev/docs/reference/ai-sdk-ui/create-ui-message-stream)
- [AI SDK Core: UIMessage](https://ai-sdk.dev/docs/reference/ai-sdk-core/ui-message)
- [AI SDK UI: Chatbot Message Persistence](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-message-persistence)
- [AI SDK Elements: Message Component](https://ai-sdk.dev/elements/components/message)
- [AI SDK Elements: Tool Component](https://ai-sdk.dev/elements/components/tool)
- [AI SDK UI: Chatbot Tool Usage](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-tool-usage)
