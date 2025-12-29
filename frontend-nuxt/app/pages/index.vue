<script setup lang="ts">
import { generateUUID } from '~/utils/uuid'

const toast = useToast()
const input = ref('')
const loading = ref(false)
const chatId = generateUUID()
const showCamera = ref(false)
const chatPromptRef = ref<{ inputRef: { el: HTMLTextAreaElement } } | null>(null)

const { model } = useModels()

const {
  isRecording,
  isPreparing,
  startRecording,
  stopRecording,
  cancelRecording
} = useAudioRecorder()

const {
  dropzoneRef,
  isDragging,
  files,
  isUploading,
  uploadedFiles,
  addFiles,
  removeFile,
  clearFiles
} = useFileUploadWithStatus(chatId)

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
function handlePaste(e: ClipboardEvent) {
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
      color: 'success'
    })
    // Fix focus after paste - small delay to ensure DOM updates
    setTimeout(() => {
      chatPromptRef.value?.inputRef?.el?.focus()
    }, 50)
  }
}

onMounted(() => {
  document.addEventListener('paste', handlePaste)
})

onUnmounted(() => {
  document.removeEventListener('paste', handlePaste)
})

async function createChat(prompt: string) {
  input.value = prompt
  loading.value = true

  const parts: Array<{ type: string, text?: string, mediaType?: string, url?: string }> = [{ type: 'text', text: prompt }]

  if (uploadedFiles.value.length > 0) {
    parts.push(...uploadedFiles.value)
  }

  const chat = await $fetch('/api/chats', {
    method: 'POST',
    body: {
      id: chatId,
      message: {
        role: 'user',
        parts
      }
    }
  })

  refreshNuxtData('chats')
  navigateTo(`/chat/${chat?.id}`)
}

async function onSubmit() {
  await createChat(input.value)
  clearFiles()
}

const quickChats = [
  {
    label: 'Buscar orden por nombre de paciente',
    icon: 'i-lucide-search'
  },
  {
    label: 'Ver resultados de una orden',
    icon: 'i-lucide-file-text'
  },
  {
    label: 'Crear una nueva orden',
    icon: 'i-lucide-plus-circle'
  },
  {
    label: 'Editar exámenes de una orden',
    icon: 'i-lucide-list-checks'
  },
  {
    label: 'Qué exámenes están disponibles?',
    icon: 'i-lucide-list'
  },
  {
    label: 'Agregar exámenes a una orden existente',
    icon: 'i-lucide-plus'
  }
]
</script>

<template>
  <UDashboardPanel id="home" :ui="{ body: 'p-0 sm:p-0' }">
    <template #header>
      <DashboardNavbar />
    </template>

    <template #body>
      <DragDropOverlay :show="isDragging" />
      <UContainer ref="dropzoneRef" class="flex-1 flex flex-col justify-center gap-4 sm:gap-6 py-8">
        <h1 class="text-3xl sm:text-4xl text-highlighted font-bold">
          ¿En qué puedo ayudarte hoy?
        </h1>

        <UChatPrompt
          ref="chatPromptRef"
          v-model="input"
          :status="loading ? 'streaming' : 'ready'"
          :disabled="isRecording"
          class="[view-transition-name:chat-prompt]"
          variant="subtle"
          :ui="{ base: 'px-1.5' }"
          @submit="onSubmit"
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

            <UChatPromptSubmit color="neutral" size="sm" :disabled="isUploading || isRecording" />
          </template>
        </UChatPrompt>

        <!-- Camera capture overlay -->
        <CameraCapture
          v-if="showCamera"
          @capture="handleCameraCapture"
          @close="showCamera = false"
        />

        <div class="flex flex-wrap gap-2">
          <UButton
            v-for="quickChat in quickChats"
            :key="quickChat.label"
            :icon="quickChat.icon"
            :label="quickChat.label"
            size="sm"
            color="neutral"
            variant="outline"
            class="rounded-full"
            @click="createChat(quickChat.label)"
          />
        </div>
      </UContainer>
    </template>
  </UDashboardPanel>
</template>
