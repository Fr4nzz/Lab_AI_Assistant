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
const { showStats } = useShowStats()
const { refreshSidebar } = useSidebarRefresh()
const tts = useTTS()

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

const {
  dropzoneRef,
  isDragging,
  files,
  isUploading,
  uploadedFiles,
  currentRotationResults,
  addFiles,
  removeFile,
  clearFiles,
  clearRotationResults,
  hasPendingRotations,
  waitForRotations
} = useFileUploadWithStatus(route.params.id as string)

// Rotation data to be sent with next message (stored in ref for transport body access)
const pendingRotationData = ref<Array<{
  fileName: string
  rotation: number
  model: string | null
  timing: { modelMs?: number; totalMs?: number }
  rotatedUrl: string
  state: string
}> | undefined>()

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
    // rotationResults is passed via ref that gets set before sendMessage
    body: () => ({
      model: model.value,
      enabledTools: enabledTools.value,
      showStats: showStats.value,
      rotationResults: pendingRotationData.value
    })
  }),
  onFinish() {
    // Clear rotation data and results after message is complete
    pendingRotationData.value = undefined
    clearRotationResults()

    // Refresh chat list to get the generated title
    setTimeout(refreshSidebar, 1000)
    setTimeout(refreshSidebar, 3000)
    setTimeout(refreshSidebar, 6000)
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

// Computed: is submission currently disabled?
const isSubmitDisabled = computed(() => {
  const disabled = isUploading.value || hasPendingRotations.value
  console.log('[isSubmitDisabled]', { isUploading: isUploading.value, hasPendingRotations: hasPendingRotations.value, result: disabled })
  return disabled
})

// Handle form submission
// NOTE: UChatPrompt @submit does NOT pass a native event - don't use e.preventDefault()
async function handleSubmit() {
  const textToSend = input.value.trim()
  const hasFiles = uploadedFiles.value.length > 0

  console.log('[handleSubmit] Called:', {
    text: textToSend.slice(0, 30),
    hasFiles,
    filesCount: files.value.length,
    hasPendingRotations: hasPendingRotations.value,
    currentRotationResults: currentRotationResults.value.map(r => ({ name: r.fileName, state: r.state }))
  })

  // Early exit if nothing to send
  if (!textToSend && !hasFiles) {
    console.log('[handleSubmit] Nothing to send, returning')
    return
  }

  // Capture completed rotation results and set in ref BEFORE sending
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

  console.log('[handleSubmit] Rotation data to send:', rotationData.length, rotationData.map(r => ({ name: r.fileName, rotation: r.rotation })))

  // Set rotation data in ref so transport body() can access it
  pendingRotationData.value = rotationData.length > 0 ? rotationData : undefined

  // Build and send message
  const message = {
    text: textToSend || ' ',
    files: hasFiles ? uploadedFiles.value : undefined
  }

  chat.sendMessage(message)

  // Clean up input and files
  input.value = ''
  clearFiles()
}


const copied = ref(false)

function copy(e: MouseEvent, message: UIMessage) {
  clipboard.copy(getTextFromMessage(message))

  copied.value = true

  setTimeout(() => {
    copied.value = false
  }, 2000)
}

// Per-message regeneration (inspired by Lobe Chat)
function regenerateMessage(messageId: string) {
  const messages = chat.messages
  const messageIndex = messages.findIndex(m => m.id === messageId)

  if (messageIndex === -1) return

  // Find the user message that triggered this response
  let userMessageIndex = messageIndex - 1
  while (userMessageIndex >= 0 && messages[userMessageIndex].role !== 'user') {
    userMessageIndex--
  }

  if (userMessageIndex < 0) return

  // Remove messages from this assistant message onward
  const newMessages = messages.slice(0, messageIndex)

  // Set the new message history and regenerate
  chat.setMessages(newMessages)
  chat.regenerate()
}

// Refocus the input after adding files - use multiple strategies for reliability
function focusInput() {
  const doFocus = () => {
    const textarea = document.querySelector('[data-chat-prompt] textarea') as HTMLTextAreaElement
    if (textarea) {
      textarea.focus()
      // Also set cursor to end of text
      const len = textarea.value.length
      textarea.setSelectionRange(len, len)
    }
  }

  // Strategy 1: nextTick (Vue's DOM update cycle)
  nextTick(doFocus)

  // Strategy 2: requestAnimationFrame (browser's next paint)
  requestAnimationFrame(doFocus)

  // Strategy 3: Multiple setTimeout backups for edge cases
  setTimeout(doFocus, 0)
  setTimeout(doFocus, 50)
  setTimeout(doFocus, 150)
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
      color: 'success',
      duration: 1500
    })
    focusInput()
  }
}

// Audio recording state
const isRecording = ref(false)
const recordingTime = ref(0)
const mediaRecorder = ref<MediaRecorder | null>(null)
const audioChunks = ref<Blob[]>([])
const recordingInterval = ref<ReturnType<typeof setInterval> | null>(null)

// Camera state
const showCamera = ref(false)

// Lightbox state
const lightboxImage = ref<{ src: string; alt?: string } | null>(null)

// Format recording time as mm:ss
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// Start audio recording
async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    mediaRecorder.value = recorder
    audioChunks.value = []

    recorder.ondataavailable = (event) => {
      audioChunks.value.push(event.data)
    }

    recorder.onstart = () => {
      isRecording.value = true
      recordingTime.value = 0
      recordingInterval.value = setInterval(() => {
        recordingTime.value++
      }, 1000)
    }

    recorder.onstop = () => {
      const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' })
      const audioFile = new File([audioBlob], `recording-${Date.now()}.webm`, { type: 'audio/webm' })
      addFiles([audioFile])
      stream.getTracks().forEach(track => track.stop())
      focusInput()
    }

    recorder.start()
  } catch (err) {
    console.error('Microphone access denied:', err)
    toast.add({
      title: 'Error',
      description: 'No se pudo acceder al micrófono',
      icon: 'i-lucide-mic-off',
      color: 'error'
    })
  }
}

// Stop audio recording
function stopRecording() {
  if (mediaRecorder.value) {
    mediaRecorder.value.stop()
    isRecording.value = false
    if (recordingInterval.value) {
      clearInterval(recordingInterval.value)
      recordingInterval.value = null
    }
  }
}

// Handle camera capture
function handleCameraCapture(file: File) {
  addFiles([file])
  showCamera.value = false
  focusInput()
}

// Handle file avatar click for lightbox
function handleFileClick(url: string, name?: string) {
  lightboxImage.value = { src: url, alt: name }
}

// Handle rotation tool image click
function handleRotationImageClick(url: string) {
  lightboxImage.value = { src: url }
}

// Group message parts into enumerated steps for assistant messages
// A step is: (optional reasoning) + (tool invocations OR final text)
interface MessageStep {
  stepNumber: number
  reasoning?: { text: string; state?: string }
  parts: Array<{ type: string; [key: string]: unknown }>
  isFinal: boolean
}

// Helper to check if a part is a tool call (handles both 'tool-invocation' and 'tool-{toolName}' patterns)
function isToolPart(part: { type: string }): boolean {
  return part.type === 'tool-invocation' || (part.type?.startsWith?.('tool-') && part.type !== 'tool-invocation')
}

// Helper to get tool state from AI SDK part
function getToolState(part: any): 'pending' | 'partial-call' | 'call' | 'result' | 'error' {
  // AI SDK uses: 'input-streaming', 'input-available', 'output-available', 'output-error'
  const state = part.state || part.status
  if (state === 'input-streaming' || state === 'partial-call') return 'partial-call'
  if (state === 'input-available' || state === 'call') return 'call'
  if (state === 'output-available' || state === 'result') return 'result'
  if (state === 'output-error' || state === 'error') return 'error'
  return 'pending'
}

// Helpers to extract rotation result data from tool part
function getRotationFromResult(part: any): number {
  const output = part.output || part.result
  if (typeof output === 'object' && output !== null) {
    return output.rotation || 0
  }
  if (typeof output === 'string') {
    try {
      const parsed = JSON.parse(output)
      return parsed.rotation || 0
    } catch {
      return 0
    }
  }
  return 0
}

function getRotatedUrlFromResult(part: any): string {
  const output = part.output || part.result
  if (typeof output === 'object' && output !== null) {
    return output.rotatedUrl || ''
  }
  if (typeof output === 'string') {
    try {
      const parsed = JSON.parse(output)
      return parsed.rotatedUrl || ''
    } catch {
      return ''
    }
  }
  return ''
}

function getModelFromResult(part: any): string | null {
  const output = part.output || part.result
  if (typeof output === 'object' && output !== null) {
    return output.model || null
  }
  if (typeof output === 'string') {
    try {
      const parsed = JSON.parse(output)
      return parsed.model || null
    } catch {
      return null
    }
  }
  return null
}

function getTimingFromResult(part: any): { modelMs?: number; totalMs?: number } | undefined {
  const output = part.output || part.result
  if (typeof output === 'object' && output !== null) {
    return output.timing || undefined
  }
  if (typeof output === 'string') {
    try {
      const parsed = JSON.parse(output)
      return parsed.timing || undefined
    } catch {
      return undefined
    }
  }
  return undefined
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
      // Handle both 'tool-invocation' and 'tool-{toolName}' patterns
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
      // Files attached by user, add to current step
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

onMounted(() => {
  // Auto-trigger AI response for messages from main page (only user message, no response yet)
  if (data.value?.messages.length === 1) {
    chat.regenerate()
  }

  // Add paste listener for images
  document.addEventListener('paste', handlePaste)
})

onUnmounted(() => {
  document.removeEventListener('paste', handlePaste)
  if (recordingInterval.value) {
    clearInterval(recordingInterval.value)
  }
})
</script>

<template>
  <UDashboardPanel id="chat" class="relative" :ui="{ body: 'p-0 sm:p-0' }">
    <template #header>
      <DashboardNavbar />
    </template>

    <template #body>
      <!-- Camera Capture Modal -->
      <CameraCapture
        v-if="showCamera"
        @capture="handleCameraCapture"
        @close="showCamera = false"
      />

      <!-- Image Lightbox -->
      <ImageLightbox
        v-if="lightboxImage"
        :src="lightboxImage.src"
        :alt="lightboxImage.alt"
        @close="lightboxImage = null"
      />

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
            <!-- User messages: show files and rotation info -->
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
                  @click="handleFileClick(part.url, getFileName(part.url))"
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
                  <!-- Special handling for rotation tool - show with thumbnail -->
                  <ToolImageRotation
                    v-else-if="isToolPart(part) && (part.type === 'tool-detect_image_rotation' || (part as any).toolName === 'detect_image_rotation')"
                    :file-name="(part as any).input?.fileName || (part as any).args?.fileName || 'imagen'"
                    :rotation="getRotationFromResult(part)"
                    :rotated-url="getRotatedUrlFromResult(part)"
                    :model="getModelFromResult(part)"
                    :timing="getTimingFromResult(part)"
                    :state="getToolState(part) === 'result' ? 'completed' : 'running'"
                    @click-image="handleRotationImageClick"
                  />
                  <!-- Handle other tool calls -->
                  <ToolLabTool
                    v-else-if="isToolPart(part)"
                    :name="(part as any).toolName || part.type?.replace?.('tool-', '')"
                    :args="(part as any).args || (part as any).input || {}"
                    :result="(part as any).result || (part as any).output"
                    :state="getToolState(part)"
                  />
                  <FileAvatar
                    v-else-if="part.type === 'file'"
                    :name="getFileName((part as any).url)"
                    :type="(part as any).mediaType"
                    :preview-url="(part as any).url"
                    @click="handleFileClick((part as any).url, getFileName((part as any).url))"
                  />
                </template>

                <!-- Message actions for assistant messages (per-message) -->
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
                      @click="tts.isSpeakingMessage(message.id) ? tts.stop() : tts.speak(getTextFromMessage(message), message.id)"
                    />
                  </UTooltip>
                </div>
              </template>
            </template>
          </template>
        </UChatMessages>

        <UChatPrompt
          v-model="input"
          :error="chat.error"
          :disabled="isSubmitDisabled"
          :placeholder="hasPendingRotations ? 'Detectando orientación de imagen...' : 'Escribe un mensaje...'"
          variant="subtle"
          class="sticky bottom-0 [view-transition-name:chat-prompt] rounded-b-none z-10"
          :ui="{ base: 'px-1.5' }"
          @submit="handleSubmit"
        >
          <template v-if="files.length > 0 || hasPendingRotations" #header>
            <div class="flex flex-col gap-2">
              <!-- Files preview -->
              <div v-if="files.length > 0" class="flex flex-wrap gap-2">
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
                  @click="handleFileClick(fileWithStatus.previewUrl, fileWithStatus.file.name)"
                />
              </div>
              <!-- Rotation detection in progress indicator -->
              <div v-if="hasPendingRotations" class="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400">
                <UIcon name="i-lucide-loader-2" class="w-4 h-4 animate-spin" />
                <span>Detectando orientación de imagen...</span>
              </div>
            </div>
          </template>

          <template #footer>
            <div class="flex items-center gap-1">
              <FileUploadButton @files-selected="addFiles($event)" />

              <!-- Microphone button -->
              <UTooltip v-if="!isRecording" text="Grabar audio">
                <UButton
                  icon="i-lucide-mic"
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  @click="startRecording"
                />
              </UTooltip>
              <UButton
                v-else
                :label="formatTime(recordingTime)"
                icon="i-lucide-square"
                color="error"
                variant="soft"
                size="sm"
                @click="stopRecording"
              />

              <!-- Camera button -->
              <UTooltip text="Tomar foto">
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
              :disabled="isSubmitDisabled"
              color="neutral"
              size="sm"
              @stop="chat.stop()"
              @reload="chat.regenerate()"
            />
          </template>
        </UChatPrompt>
      </UContainer>
    </template>
  </UDashboardPanel>
</template>
