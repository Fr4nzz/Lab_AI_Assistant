# Coding Plan: Clean Rewrite of Chat Features

## Overview

This plan addresses two non-working features:
1. **Image Rotation Tool Display** - Show rotation detection as a tool call in the AI response
2. **Chat Title Generation** - Auto-generate titles for new chats

Based on AI SDK documentation research, the root causes are:
- UChatPrompt @submit may not reliably trigger our handler
- Using transport body() for per-request data is unreliable timing
- Need to use sendMessage options.body for extra data

---

## Phase 1: Fix Message Submission Flow

### Problem
The `[handleSubmit]` log never appears, suggesting UChatPrompt doesn't trigger our @submit handler reliably.

### Solution
Replace reliance on UChatPrompt @submit with direct form handling.

### Changes

#### 1.1 Update chat/[id].vue Template

**Current:**
```vue
<UChatPrompt
  v-model="input"
  @submit="handleSubmit"
>
```

**New:**
```vue
<form @submit="handleSubmit">
  <UChatPrompt
    v-model="input"
    :submit-disabled="true"  <!-- Disable internal submit -->
  >
    <!-- Keep existing slots -->
  </UChatPrompt>
</form>
```

Or alternatively, use a custom submit button that calls handleSubmit directly.

#### 1.2 Simplify handleSubmit

**New handleSubmit:**
```typescript
async function handleSubmit(e: Event) {
  e.preventDefault();

  if (!input.value.trim() && uploadedFiles.value.length === 0) return;
  if (chat.status !== 'ready') return;

  // 1. Wait for any pending rotations
  let rotationResults: RotationResult[] = [];
  if (hasPendingRotations.value) {
    rotationResults = await waitForRotations(60000);
  } else {
    rotationResults = currentRotationResults.value.filter(r => r.state === 'completed');
  }

  // 2. Build the message
  const message = {
    text: input.value.trim() || ' ',
    files: uploadedFiles.value.length > 0 ? uploadedFiles.value : undefined
  };

  // 3. Build extra body data
  const extraBody = rotationResults.length > 0
    ? { rotationResults: rotationResults.map(r => ({
        fileName: r.fileName,
        rotation: r.rotation,
        model: r.model,
        timing: r.timing,
        rotatedUrl: r.rotatedUrl,
        state: r.state
      })) }
    : {};

  // 4. Send using AI SDK pattern - pass extra data in OPTIONS
  chat.sendMessage(message, { body: extraBody });

  // 5. Clean up
  input.value = '';
  clearFiles();
}
```

#### 1.3 Remove transport body() for rotation data

**Current:**
```typescript
transport: new DefaultChatTransport({
  api: `/api/chats/${data.value.id}`,
  body: () => ({
    model: model.value,
    rotationResults: pendingRotationResults.value  // UNRELIABLE
  })
})
```

**New:**
```typescript
transport: new DefaultChatTransport({
  api: `/api/chats/${data.value.id}`,
  body: () => ({
    model: model.value,
    enabledTools: enabledTools.value,
    showStats: showStats.value
    // NO rotationResults here - pass via sendMessage options
  })
})
```

---

## Phase 2: Backend - Fix Tool Streaming Format

### Problem
Backend streams rotation tool but frontend may not recognize it due to format issues.

### Solution
Ensure tool streaming follows exact AI SDK format.

### Changes

#### 2.1 Update stream_adapter.py

Verify tool streaming format:

```python
def tool_status(self, tool_name: str, status: str, args: dict = None,
                tool_call_id: str = None, result: Any = None) -> str:
    if status == "start":
        # First: tool-input-start
        return self._format_sse({
            "type": "tool-input-start",
            "toolCallId": tool_call_id,
            "toolName": tool_name
        })

    elif status == "args":
        # Second: tool-input-available (with complete args)
        return self._format_sse({
            "type": "tool-input-available",
            "toolCallId": tool_call_id,
            "toolName": tool_name,
            "input": args
        })

    elif status == "end":
        # Third: tool-output-available (with result)
        return self._format_sse({
            "type": "tool-output-available",
            "toolCallId": tool_call_id,
            "output": result
        })
```

#### 2.2 Update server.py rotation streaming

```python
# Stream rotation tool calls
if request.rotationResults:
    for rot in request.rotationResults:
        tool_call_id = f"rotation_{uuid.uuid4().hex[:8]}"

        # Step 1: tool-input-start
        yield adapter._format_sse({
            "type": "tool-input-start",
            "toolCallId": tool_call_id,
            "toolName": "detect_image_rotation"
        })

        # Step 2: tool-input-available
        yield adapter._format_sse({
            "type": "tool-input-available",
            "toolCallId": tool_call_id,
            "toolName": "detect_image_rotation",
            "input": {"fileName": rot.fileName}
        })

        # Step 3: tool-output-available
        yield adapter._format_sse({
            "type": "tool-output-available",
            "toolCallId": tool_call_id,
            "output": {
                "rotation": rot.rotation,
                "rotatedUrl": rot.rotatedUrl,
                "model": rot.model,
                "timing": rot.timing
            }
        })
```

---

## Phase 3: Frontend - Fix Tool Display

### Problem
Frontend checks for `tool-invocation` but AI SDK uses `tool-{toolName}`.

### Solution
Already partially implemented - verify the check is correct.

### Changes

#### 3.1 Verify isToolPart function

```typescript
function isToolPart(part: { type: string }): boolean {
  // AI SDK uses tool-{toolName} format, not tool-invocation
  return part.type?.startsWith?.('tool-') ?? false;
}
```

#### 3.2 Verify tool state mapping

```typescript
function getToolState(part: any): 'pending' | 'partial-call' | 'call' | 'result' | 'error' {
  const state = part.state;
  if (state === 'input-streaming') return 'partial-call';
  if (state === 'input-available') return 'call';
  if (state === 'output-available') return 'result';
  if (state === 'output-error') return 'error';
  return 'pending';
}
```

#### 3.3 Verify rotation tool detection

```vue
<ToolImageRotation
  v-else-if="part.type === 'tool-detect_image_rotation'"
  :file-name="part.input?.fileName"
  :rotation="part.output?.rotation"
  :rotated-url="part.output?.rotatedUrl"
  :model="part.output?.model"
  :timing="part.output?.timing"
  :state="part.state === 'output-available' ? 'completed' : 'running'"
/>
```

---

## Phase 4: Fix Title Generation

### Problem
Title generation logs not appearing - either code not reached or OPENROUTER_API_KEY not set.

### Solution
Add proper diagnostics and fix the flow.

### Changes

#### 4.1 Add startup log for API key

In `server/api/chats/[id].post.ts`, at module level:
```typescript
const config = useRuntimeConfig();
console.log('[API/chat module] OPENROUTER_API_KEY configured:', !!config.openrouterApiKey);
```

#### 4.2 Verify .env is being read

Check `nuxt.config.ts`:
```typescript
runtimeConfig: {
  openrouterApiKey: process.env.OPENROUTER_API_KEY || '',
  // ...
}
```

#### 4.3 Ensure .env file exists and has key

```
# frontend-nuxt/.env
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

---

## Phase 5: Clean Up and Remove Debug Logs

After features work:
1. Remove all `console.log` debug statements
2. Remove unused code (pendingRotationResults ref if not needed)
3. Simplify the flow

---

## Implementation Order

1. **Phase 1.1-1.3**: Fix submit handling - pass data via sendMessage options
2. **Phase 2**: Verify backend tool streaming format
3. **Phase 3**: Verify frontend tool display
4. **Phase 4**: Debug title generation
5. **Phase 5**: Clean up

---

## Testing Plan

### Test 1: Submit Handler
1. Open browser console
2. Paste an image
3. Wait for rotation to complete (watch logs)
4. Type text and press Enter or click submit
5. **Expected**: `[handleSubmit]` log appears

### Test 2: Rotation Data Sent
1. Do Test 1
2. Check Nuxt terminal for `[API/chat] rotationResults: 1 [...]`
3. **Expected**: Rotation data received by API

### Test 3: Rotation Tool Displayed
1. Do Test 2
2. Check chat UI for rotation tool card
3. **Expected**: ToolImageRotation component shows with thumbnail

### Test 4: Title Generation
1. Create new chat
2. Send first message
3. Check Nuxt terminal for `[API/chat] generateTitle called`
4. Check sidebar for title update
5. **Expected**: Chat renamed from "Nuevo Chat" to generated title

---

## Files to Modify

| File | Changes |
|------|---------|
| `app/pages/chat/[id].vue` | Fix handleSubmit, remove transport body rotation |
| `app/composables/useFileUpload.ts` | Simplify if needed |
| `server/api/chats/[id].post.ts` | Add startup diagnostics |
| `backend/server.py` | Verify rotation tool streaming format |
| `backend/stream_adapter.py` | Verify tool event format |
| `frontend-nuxt/.env` | Ensure OPENROUTER_API_KEY is set |

---

## Rollback Plan

If issues persist after changes:
1. Git revert to current commit
2. Consider alternative approach: Don't stream rotation as tool, display it separately

---

## Approval Checklist

- [ ] Plan reviewed by user
- [ ] Approach approved
- [ ] Ready to implement
