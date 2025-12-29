<script setup lang="ts">
/**
 * Camera capture component using getUserMedia.
 * Allows capturing photos from the camera.
 */
const emit = defineEmits<{
  (e: 'capture', file: File): void
  (e: 'close'): void
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const stream = ref<MediaStream | null>(null)
const error = ref<string | null>(null)
const isReady = ref(false)
const facingMode = ref<'user' | 'environment'>('environment')

async function startCamera() {
  error.value = null
  isReady.value = false

  try {
    // Stop existing stream if any
    if (stream.value) {
      stream.value.getTracks().forEach(track => track.stop())
    }

    stream.value = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: facingMode.value,
        width: { ideal: 1920 },
        height: { ideal: 1080 }
      }
    })

    if (videoRef.value) {
      videoRef.value.srcObject = stream.value
      await videoRef.value.play()
      isReady.value = true
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to access camera'
    error.value = message
    console.error('[CameraCapture] Error:', err)
  }
}

function switchCamera() {
  facingMode.value = facingMode.value === 'user' ? 'environment' : 'user'
  startCamera()
}

function capturePhoto() {
  if (!videoRef.value || !canvasRef.value) return

  const video = videoRef.value
  const canvas = canvasRef.value

  // Set canvas dimensions to match video
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight

  // Draw video frame to canvas
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

  // Convert to blob and create file
  canvas.toBlob((blob) => {
    if (blob) {
      const fileName = `camera-${Date.now()}.jpg`
      const file = new File([blob], fileName, { type: 'image/jpeg' })
      emit('capture', file)
      close()
    }
  }, 'image/jpeg', 0.9)
}

function close() {
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop())
    stream.value = null
  }
  emit('close')
}

onMounted(() => {
  startCamera()
})

onUnmounted(() => {
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop())
  }
})
</script>

<template>
  <div class="fixed inset-0 z-50 bg-black flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between p-4 bg-black/50">
      <h2 class="text-white font-medium">Capturar foto</h2>
      <UButton
        icon="i-lucide-x"
        color="white"
        variant="ghost"
        size="lg"
        @click="close"
      />
    </div>

    <!-- Video preview -->
    <div class="flex-1 relative flex items-center justify-center overflow-hidden">
      <video
        ref="videoRef"
        autoplay
        playsinline
        muted
        class="max-w-full max-h-full object-contain"
        :class="{ 'scale-x-[-1]': facingMode === 'user' }"
      />
      <canvas ref="canvasRef" class="hidden" />

      <!-- Error state -->
      <div v-if="error" class="absolute inset-0 flex items-center justify-center bg-black/80">
        <div class="text-center text-white p-4">
          <UIcon name="i-lucide-camera-off" class="w-12 h-12 mb-4 mx-auto text-red-400" />
          <p class="text-lg mb-2">No se pudo acceder a la cámara</p>
          <p class="text-sm text-gray-400">{{ error }}</p>
          <UButton
            label="Reintentar"
            color="white"
            variant="outline"
            class="mt-4"
            @click="startCamera"
          />
        </div>
      </div>

      <!-- Loading state -->
      <div v-else-if="!isReady" class="absolute inset-0 flex items-center justify-center bg-black/80">
        <UIcon name="i-lucide-loader-2" class="w-8 h-8 text-white animate-spin" />
      </div>
    </div>

    <!-- Controls -->
    <div class="flex items-center justify-center gap-6 p-6 bg-black/50">
      <!-- Switch camera button -->
      <UButton
        icon="i-lucide-switch-camera"
        color="white"
        variant="ghost"
        size="xl"
        :disabled="!isReady"
        @click="switchCamera"
      />

      <!-- Capture button -->
      <button
        class="w-16 h-16 rounded-full bg-white border-4 border-white/30 hover:bg-gray-200 transition-colors disabled:opacity-50"
        :disabled="!isReady"
        @click="capturePhoto"
      >
        <span class="sr-only">Capturar</span>
      </button>

      <!-- Placeholder for symmetry -->
      <div class="w-12" />
    </div>
  </div>
</template>
