# New Coding Plan - Fixed Analysis

## Problem Analysis

Looking at the console logs, the issue is clear:

```
[Upload] Rotation state set to 'pending' for file 3f20bc27...
[Upload] rotationResults now has 1 entries: Array(1)
...
[API/chat] rotationResults: 0 none   <-- MESSAGE SENT WHILE PENDING
...
[Upload] Rotation state set to 'completed' for file 3f20bc27...
```

**Key observation:** The `[hasPendingRotations]` debug log NEVER appears in the output!

This means the computed property is not being evaluated at the time of submission, OR there's a reactivity issue.

## Root Cause Analysis

### Issue 1: UChatPrompt disabled state doesn't check pending rotations

Current template:
```vue
<UChatPrompt
  :disabled="isUploading || isWaitingForRotationsState"  <!-- Missing hasPendingRotations! -->
  @submit="handleSubmit"
>
```

This means the form is NOT disabled while rotation is pending, allowing premature submission.

### Issue 2: Reactivity across composable boundaries

The `hasPendingRotations` computed is created inside `useFileUploadWithStatus`, but when accessed in the page component's `handleSubmit` function, Vue's computed reactivity might not trigger properly during synchronous execution.

### Issue 3: sendMessage options.body might not merge correctly

The AI SDK's `sendMessage(message, { body: { rotationResults } })` might not properly merge the per-request body with the transport body.

## Solution: Disable-First Approach

The most reliable solution is to **prevent submission entirely** until rotation is complete.

### Strategy

1. **Disable the UChatPrompt** when rotations are pending
2. **Show clear visual feedback** that rotation is in progress
3. **Auto-enable** when rotation completes
4. **No waiting logic needed** - submission is simply blocked until ready

This is simpler, more reliable, and matches how other apps handle async pre-processing.

---

## Implementation Plan

### Phase 1: Fix Submission Blocking

**Goal:** Prevent message submission while rotation is pending.

**Changes to `frontend-nuxt/app/pages/chat/[id].vue`:**

```vue
<UChatPrompt
  v-model="input"
  :error="chat.error"
  :disabled="isUploading || hasPendingRotations"  <!-- Add hasPendingRotations -->
  :placeholder="hasPendingRotations ? 'Esperando detección de rotación...' : 'Escribe un mensaje...'"
  @submit="handleSubmit"
>
```

**Simplify handleSubmit** - no need for waiting logic:

```typescript
async function handleSubmit() {
  const textToSend = input.value.trim()
  const hasFiles = uploadedFiles.value.length > 0

  if (!textToSend && !hasFiles) return

  // At this point, hasPendingRotations is false (otherwise submit was disabled)
  // Capture completed rotation results
  const rotationData = currentRotationResults.value
    .filter(r => r.state === 'completed')
    .map(r => ({
      fileName: r.fileName,
      rotation: r.rotation,
      model: r.model,
      timing: r.timing,
      rotatedUrl: r.rotatedUrl,
      state: r.state
    }))

  // Build message
  chat.sendMessage(
    { text: textToSend || ' ', files: hasFiles ? uploadedFiles.value : undefined },
    rotationData.length > 0 ? { body: { rotationResults: rotationData } } : undefined
  )

  input.value = ''
  clearFiles()
}
```

### Phase 2: Visual Rotation Feedback

**Goal:** Show clear indication that rotation detection is in progress.

**Add rotation status indicator to FileAvatar:**

The FileAvatar component should show rotation status:
- 🔄 Spinner while `state === 'pending'`
- ✅ Checkmark when `state === 'completed'`
- Rotation angle badge (e.g., "180°")

**Add status bar above prompt:**

```vue
<template v-if="hasPendingRotations" #header>
  <div class="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400 p-2">
    <UIcon name="i-lucide-loader-2" class="animate-spin" />
    <span>Detectando orientación de imagen...</span>
  </div>
</template>
```

### Phase 3: Fix Transport Body Merging

**Goal:** Ensure rotation results are properly sent to backend.

Looking at the AI SDK source, `sendMessage` options should merge with transport body. But to be safe, we should pass everything in transport body:

**Option A: Keep in transport body (more reliable)**

```typescript
const chat = new Chat({
  transport: new DefaultChatTransport({
    api: `/api/chats/${data.value.id}`,
    body: () => ({
      model: model.value,
      enabledTools: enabledTools.value,
      showStats: showStats.value,
      rotationResults: pendingRotationDataRef.value  // Use a ref, set before send
    })
  })
})

// Before sending:
pendingRotationDataRef.value = currentRotationResults.value.filter(...)
await nextTick() // Ensure reactivity
chat.sendMessage(message)
pendingRotationDataRef.value = undefined
```

**Option B: Use reactive transport body**

```typescript
const pendingRotationData = ref<RotationResult[] | undefined>()

const chat = new Chat({
  transport: new DefaultChatTransport({
    api: `/api/chats/${data.value.id}`,
    body: () => ({
      model: model.value,
      enabledTools: enabledTools.value,
      showStats: showStats.value,
      rotationResults: pendingRotationData.value
    })
  })
})
```

### Phase 4: Debug Logging

Add comprehensive logging to understand exactly what's happening:

```typescript
// In handleSubmit
console.log('[handleSubmit] Called', {
  hasPendingRotations: hasPendingRotations.value,
  filesCount: files.value.length,
  rotationResultsSize: rotationResults.value?.size,
  currentRotationResults: currentRotationResults.value
})
```

---

## Testing Checklist

1. [ ] Paste image - submit button should be disabled
2. [ ] Type message while image processing - submit still disabled
3. [ ] Wait for rotation to complete - submit becomes enabled
4. [ ] Submit - rotation results should appear in backend logs
5. [ ] Rotation tool should display in UI with thumbnail
6. [ ] Chat title should generate after first message

---

## File Changes Summary

| File | Change |
|------|--------|
| `frontend-nuxt/app/pages/chat/[id].vue` | Add hasPendingRotations to disabled, simplify handleSubmit |
| `frontend-nuxt/app/components/FileAvatar.vue` | Add rotation status indicator |

---

## Alternative: Polling Instead of Computed

If computed reactivity remains problematic, use polling:

```typescript
const isRotationPending = ref(false)

// Poll every 200ms while files exist
watchEffect(() => {
  if (files.value.length === 0) {
    isRotationPending.value = false
    return
  }

  const checkPending = () => {
    const pending = files.value.some(f => {
      if (!f.file.type.startsWith('image/')) return false
      const result = rotationResults.value.get(f.id)
      return result && (result.state === 'pending' || result.state === 'processing')
    })
    isRotationPending.value = pending

    if (pending) {
      setTimeout(checkPending, 200)
    }
  }

  checkPending()
})
```

This is more explicit and doesn't rely on Vue's computed reactivity across composable boundaries.
