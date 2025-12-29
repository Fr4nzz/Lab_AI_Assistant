# Tool Display Fix - Coding Plan

## Problem
Tool invocations display as plain text instead of styled cards with icons and badges.

## Root Cause Analysis
After investigating commit `d225596` where tools display correctly:

1. **`:assistant` prop conflict**: Current code passes `:assistant` prop to UChatMessages which may override the `#content` slot with default rendering
2. **Missing `groupMessageParts()`**: The d225596 version groups message parts into steps for proper organization
3. **No user/assistant separation**: Current code renders all message parts the same way
4. **AI SDK v5 part format**: Tools use `tool-{toolName}` format (e.g., `tool-search_orders`) with `input`/`output` properties and states like `input-streaming`, `input-available`, `output-available`, `output-error`

## Implementation Steps

### Step 1: Add `groupMessageParts()` helper function
Add after the existing helper functions:

```typescript
// Group message parts into enumerated steps for assistant messages
interface MessageStep {
  stepNumber: number
  reasoning?: { text: string; state?: string }
  parts: Array<{ type: string; [key: string]: unknown }>
  isFinal: boolean
}

function groupMessageParts(parts: Array<{ type: string; [key: string]: unknown }>): MessageStep[] {
  const steps: MessageStep[] = []
  let currentStep: MessageStep | null = null
  let stepNumber = 0

  for (const part of parts) {
    if (part.type === 'reasoning') {
      // Start a new step with reasoning
      if (currentStep && currentStep.parts.length > 0) {
        steps.push(currentStep)
      }
      stepNumber++
      currentStep = {
        stepNumber,
        reasoning: { text: part.text as string, state: part.state as string | undefined },
        parts: [],
        isFinal: false
      }
    } else if (isToolPart(part)) {
      // Add tool to current step or create new step
      if (!currentStep) {
        stepNumber++
        currentStep = { stepNumber, parts: [], isFinal: false }
      }
      currentStep.parts.push(part)
    } else if (part.type === 'text') {
      // Text is the final response
      if (!currentStep) {
        stepNumber++
        currentStep = { stepNumber, parts: [], isFinal: true }
      }
      currentStep.parts.push(part)
      currentStep.isFinal = true
    } else if (part.type === 'file') {
      // Files, add to current step
      if (!currentStep) {
        stepNumber++
        currentStep = { stepNumber, parts: [], isFinal: false }
      }
      currentStep.parts.push(part)
    }
  }

  // Push the last step
  if (currentStep) {
    steps.push(currentStep)
  }

  return steps
}
```

### Step 2: Add TTS composable import
```typescript
const tts = useTTS()
```

### Step 3: Add `regenerateMessage()` function
```typescript
function regenerateMessage(messageId: string) {
  const messages = chat.messages
  const messageIndex = messages.findIndex(m => m.id === messageId)
  if (messageIndex === -1) return

  let userMessageIndex = messageIndex - 1
  while (userMessageIndex >= 0 && messages[userMessageIndex].role !== 'user') {
    userMessageIndex--
  }
  if (userMessageIndex < 0) return

  const newMessages = messages.slice(0, messageIndex)
  chat.setMessages(newMessages)
  chat.regenerate()
}
```

### Step 4: Update UChatMessages template
Remove the `:assistant` prop and update the template:

```vue
<UChatMessages
  should-auto-scroll
  :messages="chat.messages"
  :status="chat.status"
  :spacing-offset="160"
  class="lg:pt-(--ui-header-height) pb-4 sm:pb-6 [&_[data-chat-message]]:group"
>
  <template #content="{ message }">
    <!-- User messages -->
    <template v-if="message.role === 'user'">
      <template v-for="(part, index) in message.parts" :key="`${message.id}-${part.type}-${index}`">
        <MDCCached
          v-if="part.type === 'text'"
          :value="part.text"
          :cache-key="`${message.id}-${index}`"
          :components="components"
          :parser-options="{ highlight: false }"
          class="*:first:mt-0 *:last:mb-0"
        />
        <FileAvatar
          v-else-if="part.type === 'file'"
          :name="getFileName(part.url)"
          :type="part.mediaType"
          :preview-url="part.url"
        />
      </template>
    </template>

    <!-- Assistant messages: show enumerated steps with reasoning and tools -->
    <template v-else>
      <template v-for="step in groupMessageParts(message.parts)" :key="`${message.id}-step-${step.stepNumber}`">
        <!-- Step indicator for multi-step responses -->
        <div
          v-if="groupMessageParts(message.parts).length > 1 && (step.reasoning || step.parts.some(p => isToolPart(p)))"
          class="flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500 mt-3 mb-1"
        >
          <span class="font-mono">{{ step.stepNumber }}.</span>
          <span>{{ step.isFinal ? 'Respuesta final' : 'Procesando...' }}</span>
        </div>

        <!-- Reasoning for this step -->
        <Reasoning
          v-if="step.reasoning"
          :text="step.reasoning.text"
          :is-streaming="step.reasoning.state !== 'done'"
        />

        <!-- Parts for this step (tools or text) -->
        <template v-for="(part, partIndex) in step.parts" :key="`${message.id}-step-${step.stepNumber}-part-${partIndex}`">
          <MDCCached
            v-if="part.type === 'text'"
            :value="(part as any).text"
            :cache-key="`${message.id}-step-${step.stepNumber}-${partIndex}`"
            :components="components"
            :parser-options="{ highlight: false }"
            class="*:first:mt-0 *:last:mb-0"
          />
          <ToolLabTool
            v-else-if="isToolPart(part)"
            :name="getToolName(part)"
            :args="(part as any).args || (part as any).input || {}"
            :result="(part as any).result || (part as any).output"
            :state="getToolState(part)"
          />
          <FileAvatar
            v-else-if="part.type === 'file'"
            :name="getFileName((part as any).url)"
            :type="(part as any).mediaType"
            :preview-url="(part as any).url"
          />
        </template>

        <!-- Message actions for assistant messages -->
        <div
          v-if="chat.status !== 'streaming'"
          class="flex items-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <UTooltip text="Regenerar">
            <UButton
              icon="i-lucide-rotate-ccw"
              size="xs"
              variant="ghost"
              color="neutral"
              @click="regenerateMessage(message.id)"
            />
          </UTooltip>
          <UTooltip text="Copiar">
            <UButton
              :icon="copied ? 'i-lucide-copy-check' : 'i-lucide-copy'"
              size="xs"
              variant="ghost"
              color="neutral"
              @click="copy($event, message)"
            />
          </UTooltip>
          <UTooltip v-if="tts.isSupported.value" :text="tts.isSpeakingMessage(message.id) ? 'Detener' : 'Leer en voz alta'">
            <UButton
              :icon="tts.isSpeakingMessage(message.id) ? 'i-lucide-square' : 'i-lucide-volume-2'"
              size="xs"
              variant="ghost"
              color="neutral"
              @click="tts.isSpeakingMessage(message.id) ? tts.stop() : tts.speak(message)"
            />
          </UTooltip>
        </div>
      </template>
    </template>
  </template>
</UChatMessages>
```

### Step 5: Create useTTS composable (if TTS is desired)

Create `frontend-nuxt/app/composables/useTTS.ts`:

```typescript
import type { UIMessage } from 'ai'
import { getTextFromMessage } from '@nuxt/ui/utils/ai'

/**
 * Text-to-Speech composable using browser's SpeechSynthesis API
 */
export function useTTS() {
  const isSpeaking = ref(false)
  const currentMessageId = ref<string | null>(null)

  const isSupported = computed(() => {
    return typeof window !== 'undefined' && 'speechSynthesis' in window
  })

  function speak(message: UIMessage, lang = 'es-ES') {
    if (!isSupported.value) return
    stop()

    const text = getTextFromMessage(message)
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang
    utterance.rate = 1.0
    utterance.pitch = 1.0

    utterance.onstart = () => {
      isSpeaking.value = true
      currentMessageId.value = message.id
    }
    utterance.onend = () => {
      isSpeaking.value = false
      currentMessageId.value = null
    }
    utterance.onerror = () => {
      isSpeaking.value = false
      currentMessageId.value = null
    }

    speechSynthesis.speak(utterance)
  }

  function stop() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      speechSynthesis.cancel()
    }
    isSpeaking.value = false
    currentMessageId.value = null
  }

  function isSpeakingMessage(messageId: string): boolean {
    return isSpeaking.value && currentMessageId.value === messageId
  }

  onUnmounted(() => stop())

  return { speak, stop, isSpeaking, isSupported, isSpeakingMessage }
}
```

## Files to Modify
- `frontend-nuxt/app/pages/chat/[id].vue`
- `frontend-nuxt/app/composables/useTTS.ts` (create new)

## Dependencies
- `ToolLabTool` component (already exists)

## References
- AI SDK v5 tool states: `input-streaming`, `input-available`, `output-available`, `output-error`
- Tool part type format: `tool-{toolName}` (e.g., `tool-search_orders`)
- Properties: `input` (args), `output` (result), `state`
