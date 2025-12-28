<script setup lang="ts">
const emit = defineEmits<{
  capture: [file: File]
  close: []
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const stream = ref<MediaStream | null>(null)
const error = ref<string | null>(null)

async function startCamera() {
  try {
    const mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment' }, // Prefer back camera on mobile
      audio: false
    })
    stream.value = mediaStream
    if (videoRef.value) {
      videoRef.value.srcObject = mediaStream
    }
  } catch (err) {
    console.error('Camera access denied:', err)
    error.value = 'No se pudo acceder a la cámara'
  }
}

function stopCamera() {
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop())
    stream.value = null
  }
}

function capturePhoto() {
  if (!videoRef.value) return

  const canvas = document.createElement('canvas')
  canvas.width = videoRef.value.videoWidth
  canvas.height = videoRef.value.videoHeight
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.drawImage(videoRef.value, 0, 0)
  canvas.toBlob((blob) => {
    if (blob) {
      const file = new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' })
      emit('capture', file)
    }
  }, 'image/jpeg', 0.9)
}

function handleClose() {
  stopCamera()
  emit('close')
}

// Handle escape key
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    handleClose()
  }
}

onMounted(() => {
  startCamera()
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  stopCamera()
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div
    class="fixed inset-0 z-50 bg-black/90 flex flex-col items-center justify-center p-4"
    @click="handleClose"
  >
    <div
      class="relative max-w-2xl w-full"
      @click.stop
    >
      <!-- Close button -->
      <UButton
        icon="i-lucide-x"
        color="white"
        variant="ghost"
        size="lg"
        class="absolute top-2 right-2 z-10"
        @click="handleClose"
      />

      <div v-if="error" class="bg-red-500/20 text-red-400 p-4 rounded text-center">
        {{ error }}
      </div>

      <template v-else>
        <video
          ref="videoRef"
          autoplay
          playsinline
          muted
          class="w-full rounded-lg"
        />

        <div class="flex justify-center mt-4 gap-4">
          <UButton
            icon="i-lucide-camera"
            color="white"
            size="xl"
            class="rounded-full w-16 h-16"
            @click="capturePhoto"
          />
        </div>
      </template>
    </div>
  </div>
</template>
