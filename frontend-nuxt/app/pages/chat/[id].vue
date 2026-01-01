<script setup lang="ts">
import type { DefineComponent } from 'vue'
import { Chat } from '@ai-sdk/vue'
import { DefaultChatTransport } from 'ai'
import type { UIMessage } from 'ai'
import { useClipboard } from '@vueuse/core'
import { getTextFromMessage } from '@nuxt/ui/utils/ai'
import ProseStreamPre from '../../components/prose/PreStream.vue'

const components = {
  pre: ProseStreamPre as unknown as DefineComponent
}

const route = useRoute()
const toast = useToast()
const clipboard = useClipboard()
const { model } = useModels()
const { enabledTools } = useEnabledTools()
const tts = useTTS()
const showCamera = ref(false)
const chatPromptRef = ref<{ inputRef: { el: HTMLTextAreaElement } } | null>(null)

const {
  isRecording,
  isPreparing,
  startRecording,
  stopRecording
} = useAudioRecorder()

function getFileName(url: string): string {
  try {
    const urlObj = new URL(url)
    const pathname = urlObj.pathname
    const filename = pathname.split('/').pop() || 'file'
    return decodeURIComponent(filename)
  } catch {
    return 'file'
  }
}

// Helper to check if a part is a tool call (handles both 'tool-invocation' and 'tool-{toolName}' patterns)
function isToolPart(part: { type: string }): boolean {
  return part.type === 'tool-invocation' || (part.type?.startsWith?.('tool-') && part.type !== 'tool-invocation')
}

// Helper to extract tool name from a part
function getToolName(part: any): string {
  // For 'tool-invocation' type, toolName is in the part
  if (part.type === 'tool-invocation') {
    return part.toolName || 'unknown'
  }
  // For 'tool-{toolName}' format, extract from type
  if (part.type?.startsWith?.('tool-')) {
    return part.type.replace('tool-', '')
  }
  return 'unknown'
}

// Helper to map AI SDK tool states to LabTool component states
function getToolState(part: any): 'pending' | 'partial-call' | 'call' | 'result' | 'error' {
  const state = part.state || part.status
  if (state === 'input-streaming' || state === 'partial-call') return 'partial-call'
  if (state === 'input-available' || state === 'call') return 'call'
  if (state === 'output-available' || state === 'result') return 'result'
  if (state === 'output-error' || state === 'error') return 'error'
  return 'pending'
}

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
      if (!currentStep) {
        stepNumber++
        currentStep = { stepNumber, parts: [], isFinal: false }
      }
      currentStep.parts.push(part)
    } else if (part.type === 'text') {
      if (!currentStep) {
        stepNumber++
        currentStep = { stepNumber, parts: [], isFinal: true }
      }
      currentStep.parts.push(part)
      currentStep.isFinal = true
    } else if (part.type === 'file') {
      if (!currentStep) {
        stepNumber++
        currentStep = { stepNumber, parts: [], isFinal: false }
      }
      currentStep.parts.push(part)
    }
  }

  if (currentStep) {
    steps.push(currentStep)
  }

  return steps
}

const {
  dropzoneRef,
  isDragging,
  files,
  isUploading,
  uploadedFiles,
  addFiles,
  removeFile,
  clearFiles,
  waitForPendingRotations
} = useFileUploadWithStatus(route.params.id as string)

const { data } = await useFetch(`/api/chats/${route.params.id}`, {
  cache: 'force-cache'
})
if (!data.value) {
  throw createError({ statusCode: 404, statusMessage: 'Chat not found' })
}

// Transform messages to include parts if they only have content
const transformedMessages = (data.value.messages || []).map((msg: any) => ({
  id: msg.id,
  role: msg.role,
  createdAt: msg.createdAt,
  parts: msg.parts || (msg.content ? [{ type: 'text', text: msg.content }] : [])
}))

const input = ref('')

const chat = new Chat({
  id: data.value.id,
  messages: transformedMessages,
  transport: new DefaultChatTransport({
    api: `/api/chats/${data.value.id}`,
    body: () => ({
      model: model.value,
      enabledTools: enabledTools.value
    })
  }),
  onFinish() {
    // Refresh chat list to get updated title
    refreshNuxtData('chats')
    // Title generation is async and may complete after stream ends
    // Add delayed refreshes to catch the title update
    setTimeout(() => refreshNuxtData('chats'), 3000)
    setTimeout(() => refreshNuxtData('chats'), 8000)
  },
  onError(error) {
    const { message } = typeof error.message === 'string' && error.message[0] === '{' ? JSON.parse(error.message) : error
    toast.add({
      description: message,
      icon: 'i-lucide-alert-circle',
      color: 'error',
      duration: 0
    })
  }
})

async function handleSubmit(e: Event) {
  e.preventDefault()
  if (input.value.trim() && !isRecording.value) {
    // Wait for any pending rotation detections to complete
    // This ensures rotated images are sent with correct orientation
    await waitForPendingRotations()

    chat.sendMessage({
      text: input.value,
      files: uploadedFiles.value.length > 0 ? uploadedFiles.value : undefined
    })
    input.value = ''
    clearFiles()
  }
}

const copied = ref(false)

function copy(e: MouseEvent, message: UIMessage) {
  clipboard.copy(getTextFromMessage(message))

  copied.value = true

  setTimeout(() => {
    copied.value = false
  }, 2000)
}

// Per-message regeneration
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

// Microphone recording handlers
async function toggleRecording() {
  if (isRecording.value) {
    const audioFile = await stopRecording()
    if (audioFile) {
      addFiles([audioFile])
      toast.add({
        title: 'Audio grabado',
        description: 'Grabación de audio agregada',
        icon: 'i-lucide-mic',
        color: 'success'
      })
    }
  } else {
    try {
      await startRecording()
    } catch {
      toast.add({
        title: 'Error',
        description: 'No se pudo acceder al micrófono',
        icon: 'i-lucide-mic-off',
        color: 'error'
      })
    }
  }
}

// Camera capture handler
function handleCameraCapture(file: File) {
  addFiles([file])
  showCamera.value = false
  toast.add({
    title: 'Foto capturada',
    description: 'Imagen agregada',
    icon: 'i-lucide-camera',
    color: 'success'
  })
}

// Handle clipboard paste for images
async function handlePaste(e: ClipboardEvent) {
  const items = e.clipboardData?.items
  if (!items) return

  const imageFiles: File[] = []

  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const blob = item.getAsFile()
      if (blob) {
        // Create a proper file with a name
        const extension = item.type.split('/')[1] || 'png'
        const fileName = `pasted-image-${Date.now()}.${extension}`
        const file = new File([blob], fileName, { type: item.type })
        imageFiles.push(file)
      }
    }
  }

  if (imageFiles.length > 0) {
    e.preventDefault()
    addFiles(imageFiles)
    toast.add({
      title: 'Imagen pegada',
      description: `${imageFiles.length} imagen(es) agregada(s)`,
      icon: 'i-lucide-image',
      color: 'success'
    })
    // Fix focus after paste - small delay to ensure DOM updates
    setTimeout(() => {
      chatPromptRef.value?.inputRef?.el?.focus()
    }, 50)
  }
}

onMounted(() => {
  if (data.value?.messages.length === 1) {
    chat.regenerate()
  }

  // Add paste listener for images
  document.addEventListener('paste', handlePaste)
})

onUnmounted(() => {
  document.removeEventListener('paste', handlePaste)
})
</script>

<template>
  <UDashboardPanel id="chat" class="relative" :ui="{ body: 'p-0 sm:p-0' }">
    <template #header>
      <DashboardNavbar />
    </template>

    <template #body>
      <DragDropOverlay :show="isDragging" />
      <UContainer ref="dropzoneRef" class="flex-1 flex flex-col gap-4 sm:gap-6">
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
                  :name="getFileName((part as any).originalUrl || part.url)"
                  :type="part.mediaType"
                  :preview-url="(part as any).originalUrl || part.url"
                  :rotation="(part as any).rotation || 0"
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
                    :name="getFileName((part as any).originalUrl || (part as any).url)"
                    :type="(part as any).mediaType"
                    :preview-url="(part as any).originalUrl || (part as any).url"
                    :rotation="(part as any).rotation || 0"
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

        <UChatPrompt
          ref="chatPromptRef"
          v-model="input"
          :error="chat.error"
          :disabled="isRecording"
          variant="subtle"
          class="sticky bottom-0 [view-transition-name:chat-prompt] rounded-b-none z-10"
          :ui="{ base: 'px-1.5' }"
          @submit="handleSubmit"
        >
          <template v-if="files.length > 0" #header>
            <div class="flex flex-wrap gap-2">
              <FileAvatar
                v-for="fileWithStatus in files"
                :key="fileWithStatus.id"
                :name="fileWithStatus.file.name"
                :type="fileWithStatus.file.type"
                :preview-url="fileWithStatus.previewUrl"
                :status="fileWithStatus.status"
                :error="fileWithStatus.error"
                :rotation="fileWithStatus.rotation"
                removable
                @remove="removeFile(fileWithStatus.id)"
              />
            </div>
          </template>

          <template #footer>
            <div class="flex items-center gap-1">
              <FileUploadButton @files-selected="addFiles($event)" />

              <!-- Microphone button -->
              <UTooltip :text="isRecording ? 'Detener grabación' : 'Grabar audio'">
                <UButton
                  :icon="isRecording ? 'i-lucide-square' : 'i-lucide-mic'"
                  :color="isRecording ? 'error' : 'neutral'"
                  variant="ghost"
                  size="sm"
                  :loading="isPreparing"
                  @click="toggleRecording"
                />
              </UTooltip>

              <!-- Camera button -->
              <UTooltip text="Capturar foto">
                <UButton
                  icon="i-lucide-camera"
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  @click="showCamera = true"
                />
              </UTooltip>

              <ModelSelect v-model="model" />
            </div>

            <UChatPromptSubmit
              :status="chat.status"
              :disabled="isUploading || isRecording"
              color="neutral"
              size="sm"
              @stop="chat.stop()"
              @reload="chat.regenerate()"
            />
          </template>
        </UChatPrompt>

        <!-- Camera capture overlay -->
        <CameraCapture
          v-if="showCamera"
          @capture="handleCameraCapture"
          @close="showCamera = false"
        />
      </UContainer>
    </template>
  </UDashboardPanel>
</template>
