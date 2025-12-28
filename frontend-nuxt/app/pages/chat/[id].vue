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
  rotatedFilesInfo,
  addFiles,
  removeFile,
  clearFiles
} = useFileUploadWithStatus(route.params.id as string)

// Store rotation info per message ID so it persists after files are cleared
const messageRotationInfo = ref<Map<string, Array<{
  fileName: string
  rotation: number
  model: string | null
  timing: { modelMs?: number; totalMs?: number }
  rotatedUrl: string
}>>>(new Map())

const { data } = await useFetch(`/api/chats/${route.params.id}`, {
  cache: 'force-cache'
})
if (!data.value) {
  throw createError({ statusCode: 404, statusMessage: 'Chat not found' })
}

// Transform messages to include parts if they only have content
// IMPORTANT: This must be a static value, NOT a computed
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
      enabledTools: enabledTools.value,
      showStats: showStats.value
    })
  }),
  onFinish() {
    // Poll for chat list updates to get the generated title
    // Title generation is async and may take a few seconds
    const refreshTimes = [500, 2000, 5000]
    refreshTimes.forEach(delay => {
      setTimeout(() => {
        refreshNuxtData('chats')
      }, delay)
    })
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

// IMPORTANT: handleSubmit must have required Event parameter
async function handleSubmit(e: Event) {
  e.preventDefault()
  const textToSend = input.value.trim()
  const hasFiles = uploadedFiles.value.length > 0

  // Allow sending with just files OR just text OR both
  if ((textToSend || hasFiles) && !isUploading.value) {
    // Save rotation info before clearing files
    // We'll associate it with the next message (which will be the user message being sent)
    if (rotatedFilesInfo.value.length > 0) {
      pendingRotationInfo.value = [...rotatedFilesInfo.value]
    }

    chat.sendMessage({
      // Use space as fallback when sending files-only (AI SDK requirement)
      text: textToSend || (hasFiles ? ' ' : ''),
      files: hasFiles ? uploadedFiles.value : undefined
    })
    input.value = ''
    clearFiles()
  }
}

// Pending rotation info to be associated with the next user message
const pendingRotationInfo = ref<Array<{
  fileName: string
  rotation: number
  model: string | null
  timing: { modelMs?: number; totalMs?: number }
  rotatedUrl: string
}>>([])

// Watch for new messages to associate rotation info
watch(() => chat.messages.length, (newLen, oldLen) => {
  if (newLen > oldLen && pendingRotationInfo.value.length > 0) {
    // Find the latest user message
    const latestUserMessage = [...chat.messages].reverse().find(m => m.role === 'user')
    if (latestUserMessage) {
      messageRotationInfo.value.set(latestUserMessage.id, [...pendingRotationInfo.value])
      pendingRotationInfo.value = []
    }
  }
})

const copied = ref(false)

function copy(e: MouseEvent, message: UIMessage) {
  clipboard.copy(getTextFromMessage(message))

  copied.value = true

  setTimeout(() => {
    copied.value = false
  }, 2000)
}

// Refocus the input after adding files
function focusInput() {
  requestAnimationFrame(() => {
    const textarea = document.querySelector('[data-chat-prompt] textarea') as HTMLTextAreaElement
    if (textarea) {
      textarea.focus()
    }
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
          :assistant="chat.status !== 'streaming' ? { actions: [{ label: 'Copiar', icon: copied ? 'i-lucide-copy-check' : 'i-lucide-copy', onClick: copy }] } : { actions: [] }"
          :spacing-offset="160"
          class="lg:pt-(--ui-header-height) pb-4 sm:pb-6"
        >
          <template #content="{ message }">
            <template v-for="(part, index) in message.parts" :key="`${message.id}-${part.type}-${index}${'state' in part ? `-${part.state}` : ''}`">
              <Reasoning
                v-if="part.type === 'reasoning'"
                :text="part.text"
                :is-streaming="part.state !== 'done'"
              />
              <MDCCached
                v-else-if="part.type === 'text'"
                :value="part.text"
                :cache-key="`${message.id}-${index}`"
                :components="components"
                :parser-options="{ highlight: false }"
                class="*:first:mt-0 *:last:mb-0"
              />
              <!-- Lab tool invocations -->
              <ToolLabTool
                v-else-if="part.type === 'tool-invocation'"
                :name="(part as any).toolName"
                :args="(part as any).args || {}"
                :result="(part as any).result"
                :state="(part as any).state || 'pending'"
              />
              <FileAvatar
                v-else-if="part.type === 'file'"
                :name="getFileName(part.url)"
                :type="part.mediaType"
                :preview-url="part.url"
                @click="handleFileClick(part.url, getFileName(part.url))"
              />
            </template>

            <!-- Show rotation info for user messages that had images rotated -->
            <template v-if="message.role === 'user' && messageRotationInfo.get(message.id)">
              <ToolImageRotation
                v-for="(info, idx) in messageRotationInfo.get(message.id)"
                :key="`rotation-${message.id}-${idx}`"
                :file-name="info.fileName"
                :rotation="info.rotation"
                :rotated-url="info.rotatedUrl"
                :model="info.model"
                :timing="info.timing"
                @click-image="handleRotationImageClick"
              />
            </template>
          </template>
        </UChatMessages>

        <UChatPrompt
          v-model="input"
          :error="chat.error"
          :disabled="isUploading"
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
                @click="handleFileClick(fileWithStatus.previewUrl, fileWithStatus.file.name)"
              />
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
              :disabled="isUploading"
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
