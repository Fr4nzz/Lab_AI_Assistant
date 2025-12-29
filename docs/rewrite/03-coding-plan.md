# Coding Plan: Clean Rewrite of Chat Features

## Overview

This plan addresses broken features and adds improvements based on Lobe Chat analysis:

**Broken Features:**
1. **Image Rotation Tool Display** - Rotation detection happens but tool is not shown in UI
2. **Chat Title Generation** - New chats remain "Nuevo Chat" instead of getting auto-generated titles

**New Features (from Lobe Chat):**
3. **Per-message Regenerate** - Regenerate any assistant message
4. **Read Aloud (TTS)** - Text-to-speech using browser API
5. **Better Message Actions** - Dropdown menu with actions

---

## Phase 1: Fix Message Submission Flow

### Problem
The `[handleSubmit]` log never appears, suggesting UChatPrompt doesn't trigger our @submit handler reliably.

### Solution
Pass rotation data via `sendMessage` options instead of transport body().

### Changes

#### 1.1 Simplify handleSubmit - Use sendMessage options.body

**Key insight from AI SDK docs:** `sendMessage` accepts a second parameter for per-request body data:
```typescript
chat.sendMessage(message, { body: { customData: 'value' } })
```

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

  // 3. Pass rotation data via sendMessage OPTIONS (not transport body)
  chat.sendMessage(message, {
    body: rotationResults.length > 0 ? {
      rotationResults: rotationResults.map(r => ({
        fileName: r.fileName,
        rotation: r.rotation,
        model: r.model,
        timing: r.timing,
        rotatedUrl: r.rotatedUrl,
        state: r.state
      }))
    } : undefined
  });

  // 4. Clean up
  input.value = '';
  clearFiles();
}
```

#### 1.2 Remove rotation data from transport body

```typescript
transport: new DefaultChatTransport({
  api: `/api/chats/${data.value.id}`,
  body: () => ({
    model: model.value,
    enabledTools: enabledTools.value,
    showStats: showStats.value
    // NO rotationResults - pass via sendMessage options
  })
})
```

#### 1.3 Remove pendingRotationResults ref

No longer needed - we pass data directly with sendMessage.

---

## Phase 2: Fix Title Generation

### Problem
Title generation not working - possibly env var not set or code path not reached.

### Solution
Improve prompt based on Lobe Chat's approach and add better debugging.

### Changes

#### 2.1 Update title generation prompt (from Lobe Chat)

```typescript
const TITLE_SYSTEM_PROMPT = `You are a professional conversation summarizer. Generate a concise title that captures the essence of the conversation.

Rules:
- Output ONLY the title text, no explanations or additional context
- Maximum 10 words
- Maximum 50 characters
- No punctuation marks
- Use the language: Spanish
- The title should accurately reflect the main topic of the conversation
- Keep it short and to the point`;
```

#### 2.2 Add startup validation

In `server/api/chats/[id].post.ts`:
```typescript
// At module load time
const config = useRuntimeConfig();
if (!config.openrouterApiKey) {
  console.warn('[API/chat] WARNING: OPENROUTER_API_KEY not configured - title generation disabled');
}
```

#### 2.3 Ensure .env has OPENROUTER_API_KEY

```bash
# frontend-nuxt/.env
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

---

## Phase 3: Backend - Fix Tool Streaming Format

### Problem
Backend streams rotation tool but format may not match AI SDK expectations.

### Solution
Ensure exact AI SDK stream protocol format.

### Changes

#### 3.1 Verify tool streaming format

Backend must send these events in order:
```json
{"type":"tool-input-start","toolCallId":"rotation_123","toolName":"detect_image_rotation"}
{"type":"tool-input-available","toolCallId":"rotation_123","toolName":"detect_image_rotation","input":{"fileName":"image.jpg"}}
{"type":"tool-output-available","toolCallId":"rotation_123","output":{"rotation":180,"rotatedUrl":"..."}}
```

#### 3.2 Update stream_adapter.py

```python
def stream_rotation_tool(self, rotation_result):
    tool_call_id = f"rotation_{uuid.uuid4().hex[:8]}"

    # 1. tool-input-start
    yield self._format_sse({
        "type": "tool-input-start",
        "toolCallId": tool_call_id,
        "toolName": "detect_image_rotation"
    })

    # 2. tool-input-available
    yield self._format_sse({
        "type": "tool-input-available",
        "toolCallId": tool_call_id,
        "toolName": "detect_image_rotation",
        "input": {"fileName": rotation_result.fileName}
    })

    # 3. tool-output-available
    yield self._format_sse({
        "type": "tool-output-available",
        "toolCallId": tool_call_id,
        "output": {
            "rotation": rotation_result.rotation,
            "rotatedUrl": rotation_result.rotatedUrl,
            "model": rotation_result.model,
            "timing": rotation_result.timing
        }
    })
```

---

## Phase 4: Frontend - Fix Tool Display

### Problem
Frontend may not recognize tool parts correctly.

### Solution
Verify tool part detection matches AI SDK format.

### Changes

#### 4.1 Tool part type is `tool-{toolName}`

AI SDK creates parts with type `tool-detect_image_rotation`, not `tool-invocation`.

```typescript
function isToolPart(part: { type: string }): boolean {
  return part.type?.startsWith?.('tool-') ?? false;
}
```

#### 4.2 Tool state mapping

```typescript
function getToolState(part: any): string {
  const state = part.state;
  if (state === 'input-streaming') return 'partial-call';
  if (state === 'input-available') return 'call';
  if (state === 'output-available') return 'result';
  if (state === 'output-error') return 'error';
  return 'pending';
}
```

#### 4.3 Access tool data from correct properties

```vue
<ToolImageRotation
  v-if="part.type === 'tool-detect_image_rotation'"
  :file-name="part.input?.fileName"
  :rotation="part.output?.rotation"
  :rotated-url="part.output?.rotatedUrl"
  :model="part.output?.model"
  :timing="part.output?.timing"
  :state="part.state === 'output-available' ? 'completed' : 'running'"
/>
```

---

## Phase 5: Add Per-Message Regenerate (New Feature)

### Inspiration
Lobe Chat allows regenerating any assistant message, not just the last one.

### Implementation

#### 5.1 Add regenerate button to message actions

In the template:
```vue
<template #content="{ message }">
  <div v-if="message.role === 'assistant'" class="message-actions">
    <UButton
      icon="i-lucide-rotate-ccw"
      size="xs"
      variant="ghost"
      @click="regenerateMessage(message.id)"
    />
  </div>
</template>
```

#### 5.2 Implement regenerateMessage function

```typescript
async function regenerateMessage(messageId: string) {
  const messages = chat.messages;
  const messageIndex = messages.findIndex(m => m.id === messageId);

  if (messageIndex === -1) return;

  // Find the user message that triggered this response
  let userMessageIndex = messageIndex - 1;
  while (userMessageIndex >= 0 && messages[userMessageIndex].role !== 'user') {
    userMessageIndex--;
  }

  if (userMessageIndex < 0) return;

  // Remove messages from this assistant message onward
  const newMessages = messages.slice(0, messageIndex);

  // Resend from the user message
  chat.setMessages(newMessages);
  chat.regenerate();
}
```

---

## Phase 6: Add Read Aloud / TTS (New Feature)

### Inspiration
Lobe Chat has TTS with multiple providers. We'll start simple with browser API.

### Implementation

#### 6.1 Create useTTS composable

```typescript
// composables/useTTS.ts
export function useTTS() {
  const isSpeaking = ref(false);
  const currentUtterance = ref<SpeechSynthesisUtterance | null>(null);

  function speak(text: string, lang = 'es-ES') {
    stop(); // Stop any current speech

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = 1.0;

    utterance.onstart = () => { isSpeaking.value = true; };
    utterance.onend = () => { isSpeaking.value = false; };
    utterance.onerror = () => { isSpeaking.value = false; };

    currentUtterance.value = utterance;
    speechSynthesis.speak(utterance);
  }

  function stop() {
    speechSynthesis.cancel();
    isSpeaking.value = false;
  }

  return { speak, stop, isSpeaking };
}
```

#### 6.2 Add TTS button to message actions

```vue
<UButton
  :icon="isSpeaking ? 'i-lucide-square' : 'i-lucide-play'"
  size="xs"
  variant="ghost"
  @click="isSpeaking ? tts.stop() : tts.speak(getTextFromMessage(message))"
/>
```

---

## Phase 7: Improve Message Actions UI

### Inspiration
Lobe Chat uses a clean action bar with dropdown menu.

### Implementation

#### 7.1 Create MessageActions component

```vue
<!-- components/MessageActions.vue -->
<template>
  <div class="flex items-center gap-1">
    <!-- Primary actions (always visible) -->
    <UButton
      v-for="action in primaryActions"
      :key="action.key"
      :icon="action.icon"
      size="xs"
      variant="ghost"
      :disabled="action.disabled"
      @click="emit('action', action.key)"
    />

    <!-- Dropdown menu for secondary actions -->
    <UDropdownMenu :items="menuItems">
      <UButton icon="i-lucide-more-horizontal" size="xs" variant="ghost" />
    </UDropdownMenu>
  </div>
</template>
```

---

## Implementation Order

### Week 1: Fix Broken Features
1. **Phase 1**: Fix message submission (sendMessage options.body)
2. **Phase 3**: Verify backend tool streaming format
3. **Phase 4**: Verify frontend tool display
4. **Phase 2**: Fix title generation with better prompt

### Week 2: Add New Features
5. **Phase 5**: Per-message regenerate
6. **Phase 6**: Read aloud (TTS)
7. **Phase 7**: Message actions UI

### Week 3: Clean Up
8. Remove all debug console.log statements
9. Add tests
10. Update documentation

---

## Files to Modify

| Phase | File | Changes |
|-------|------|---------|
| 1 | `app/pages/chat/[id].vue` | Use sendMessage options.body |
| 1 | `app/pages/chat/[id].vue` | Remove pendingRotationResults |
| 2 | `server/api/chats/[id].post.ts` | Better prompt, startup validation |
| 3 | `backend/stream_adapter.py` | Verify tool event format |
| 3 | `backend/server.py` | Verify rotation streaming |
| 4 | `app/pages/chat/[id].vue` | Fix tool part detection |
| 5 | `app/pages/chat/[id].vue` | Add regenerateMessage |
| 6 | `app/composables/useTTS.ts` | New file |
| 6 | `app/pages/chat/[id].vue` | Add TTS button |
| 7 | `app/components/MessageActions.vue` | New file |

---

## Testing Plan

### Test 1: Rotation Tool Display
1. Paste an image in chat
2. Wait for rotation detection to complete
3. Send message
4. **Expected**: Rotation tool appears in AI response with thumbnail

### Test 2: Title Generation
1. Create new chat
2. Send first message
3. **Expected**: Chat title updates from "Nuevo Chat" to generated title

### Test 3: Per-Message Regenerate
1. Have a conversation with multiple messages
2. Click regenerate on an earlier assistant message
3. **Expected**: That message and all following are replaced

### Test 4: TTS
1. Get an assistant response
2. Click play/read aloud button
3. **Expected**: Message is spoken aloud
4. Click stop button
5. **Expected**: Speech stops

---

## Rollback Plan

If issues persist:
1. Git revert to before changes
2. Consider alternative: Display rotation info separately, not as tool call

---

## Approval Checklist

- [ ] Plan reviewed by user
- [ ] Broken features approach approved
- [ ] New features approved (regenerate, TTS)
- [ ] Implementation order approved
- [ ] Ready to implement
