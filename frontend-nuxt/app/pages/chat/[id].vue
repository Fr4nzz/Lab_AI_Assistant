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

// Lightbox state
const lightboxImage = ref<{ src: string; alt: string } | null>(null)

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
  addFiles,
  removeFile,
  clearFiles
} = useFileUploadWithStatus(route.params.id as string)

const { data } = await useFetch(`/api/chats/${route.params.id}`, {
  cache: 'force-cache'
})
if (!data.value) {
  throw createError({ statusCode: 404, statusMessage: 'Chat not found' })
}

// Transform messages to include parts if they only have content
// Filter out duplicate messages by checking if assistant response exists
const transformedMessages = computed(() => {
  const msgs = data.value?.messages || []
  // Only return messages that were saved to DB (have content)
  return msgs
    .filter((msg: any) => msg.content || (msg.parts && msg.parts.length > 0))
    .map((msg: any) => ({
      id: msg.id,
      role: msg.role,
      createdAt: msg.createdAt,
      parts: msg.parts || (msg.content ? [{ type: 'text', text: msg.content }] : [])
    }))
})

const input = ref('')

const chat = new Chat({
  id: data.value.id,
  messages: transformedMessages.value,
  transport: new DefaultChatTransport({
    api: `/api/chats/${data.value.id}`,
    body: () => ({
      model: model.value,
      enabledTools: enabledTools.value,
      showStats: showStats.value
    })
  }),
  onFinish() {
    // Refresh chat list after a delay to get updated title
    // Title generation is async and may take a few seconds
    setTimeout(() => {
      refreshNuxtData('chats')
    }, 1500)
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

async function handleSubmit(e?: Event) {
  if (e) e.preventDefault()

  console.log('=== HANDLE SUBMIT CALLED ===')
  console.log('input:', input.value)
  console.log('isUploading:', isUploading.value)
  console.log('uploadedFiles:', uploadedFiles.value.length)

  const hasText = input.value.trim().length > 0
  const hasFiles = uploadedFiles.value.length > 0

  if ((hasText || hasFiles) && !isUploading.value) {
    console.log('=== SENDING MESSAGE ===')
    try {
      chat.sendMessage({
        text: input.value || ' ',
        files: hasFiles ? uploadedFiles.value : undefined
      })
      console.log('=== sendMessage called successfully ===')
    } catch (err) {
      console.error('=== sendMessage ERROR ===', err)
    }
    input.value = ''
    clearFiles()
  } else {
    console.log('=== SUBMIT BLOCKED ===', { hasText, hasFiles, isUploading: isUploading.value })
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

// Refocus the input after adding files
function focusInput() {
  nextTick(() => {
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
    // Use a shorter, less intrusive notification
    toast.add({
      description: `${imageFiles.length} imagen(es) pegada(s)`,
      icon: 'i-lucide-image',
      color: 'success',
      duration: 1500
    })
    // Keep focus on input after paste - use setTimeout to ensure focus after toast
    setTimeout(() => focusInput(), 50)
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

// Open image in lightbox
function openLightbox(url: string, name: string) {
  lightboxImage.value = { src: url, alt: name }
}

onMounted(() => {
  // Add paste listener for images
  document.addEventListener('paste', handlePaste)
})

onUnmounted(() => {
  document.removeEventListener('paste', handlePaste)
  // Clean up recording interval
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
      <!-- Image Lightbox -->
      <ImageLightbox
        v-if="lightboxImage"
        :src="lightboxImage.src"
        :alt="lightboxImage.alt"
        @close="lightboxImage = null"
      />

      <!-- Camera Capture Modal -->
      <CameraCapture
        v-if="showCamera"
        @capture="handleCameraCapture"
        @close="showCamera = false"
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
                @click="openLightbox(part.url, getFileName(part.url))"
              />
            </template>
          </template>
        </UChatMessages>

        <UChatPrompt
          v-model="input"
          :error="chat.error"
          :disabled="isRecording"
          variant="subtle"
          class="sticky bottom-0 [view-transition-name:chat-prompt] rounded-b-none z-10"
          :ui="{ base: 'px-1.5' }"
          data-chat-prompt
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
                @click="fileWithStatus.previewUrl && openLightbox(fileWithStatus.previewUrl, fileWithStatus.file.name)"
              />
            </div>
          </template>

          <template #footer>
            <div class="flex items-center gap-1">
              <!-- DEBUG: Test button -->
              <UButton
                size="xs"
                color="error"
                @click="() => { console.log('TEST BUTTON CLICKED'); handleSubmit(); }"
              >
                TEST
              </UButton>

              <FileUploadButton @files-selected="addFiles($event); focusInput()" />

              <!-- Camera button -->
              <UTooltip text="Tomar foto">
                <UButton
                  icon="i-lucide-camera"
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  :disabled="isRecording"
                  class="hidden sm:flex"
                  @click="showCamera = true"
                />
              </UTooltip>

              <!-- Audio recording button -->
              <UTooltip :text="isRecording ? 'Detener grabación' : 'Grabar audio'">
                <UButton
                  :icon="isRecording ? 'i-lucide-square' : 'i-lucide-mic'"
                  :color="isRecording ? 'error' : 'neutral'"
                  :variant="isRecording ? 'solid' : 'ghost'"
                  size="sm"
                  :disabled="chat.status === 'streaming'"
                  @click="isRecording ? stopRecording() : startRecording()"
                >
                  <template v-if="isRecording">
                    <span class="text-xs font-mono ml-1">{{ formatTime(recordingTime) }}</span>
                  </template>
                </UButton>
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
              @click="handleSubmit"
            />
          </template>
        </UChatPrompt>
      </UContainer>
    </template>
  </UDashboardPanel>
</template>
