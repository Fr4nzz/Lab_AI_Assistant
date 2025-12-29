<script setup lang="ts">
interface FileAvatarProps {
  name: string
  type: string
  previewUrl?: string
  status?: 'idle' | 'uploading' | 'uploaded' | 'error'
  error?: string
  removable?: boolean
  rotation?: number
}

const props = withDefaults(defineProps<FileAvatarProps>(), {
  status: 'idle',
  removable: false,
  rotation: 0
})

const emit = defineEmits<{
  remove: []
}>()

const showLightbox = ref(false)
const isPlaying = ref(false)
const audioRef = ref<HTMLAudioElement | null>(null)
const videoRef = ref<HTMLVideoElement | null>(null)

const isImage = computed(() => props.type.startsWith('image/'))
const isAudio = computed(() => props.type.startsWith('audio/'))
const isVideo = computed(() => props.type.startsWith('video/'))
const isMedia = computed(() => isAudio.value || isVideo.value)

// Rotation degrees to CSS transform
const rotationStyle = computed(() => {
  if (!props.rotation) return {}
  return {
    transform: `rotate(${props.rotation}deg)`
  }
})

function handleClick() {
  if (props.status === 'uploading') return

  if (isImage.value && props.previewUrl) {
    showLightbox.value = true
  } else if (isMedia.value && props.previewUrl) {
    togglePlayback()
  }
}

function togglePlayback() {
  if (isAudio.value && audioRef.value) {
    if (isPlaying.value) {
      audioRef.value.pause()
      audioRef.value.currentTime = 0
    } else {
      audioRef.value.play()
    }
  } else if (isVideo.value && videoRef.value) {
    if (isPlaying.value) {
      videoRef.value.pause()
      videoRef.value.currentTime = 0
    } else {
      videoRef.value.play()
    }
  }
  isPlaying.value = !isPlaying.value
}

function handleMediaEnded() {
  isPlaying.value = false
}
</script>

<template>
  <div class="relative group">
    <UTooltip arrow :text="removeRandomSuffix(name)">
      <div
        class="cursor-pointer"
        @click="handleClick"
      >
        <UAvatar
          size="3xl"
          :src="isImage ? previewUrl : undefined"
          :icon="getFileIcon(type, name)"
          class="border border-default rounded-lg transition-transform"
          :class="{
            'opacity-50': status === 'uploading',
            'border-error': status === 'error',
            'hover:ring-2 ring-primary': (isImage || isMedia) && previewUrl && status !== 'uploading'
          }"
          :style="isImage ? rotationStyle : {}"
        />
      </div>
    </UTooltip>

    <!-- Rotation badge -->
    <div
      v-if="rotation && rotation !== 0"
      class="absolute -top-1 -left-1 bg-primary text-primary-foreground rounded-full px-1.5 py-0.5 text-xs font-medium flex items-center gap-0.5"
    >
      <UIcon name="i-lucide-rotate-cw" class="w-3 h-3" />
      {{ rotation }}
    </div>

    <!-- Play/Pause overlay for audio/video -->
    <div
      v-if="isMedia && previewUrl && status !== 'uploading'"
      class="absolute inset-0 flex items-center justify-center bg-black/30 rounded-lg cursor-pointer"
      @click="handleClick"
    >
      <UIcon
        :name="isPlaying ? 'i-lucide-pause' : 'i-lucide-play'"
        class="size-8 text-white"
      />
    </div>

    <div
      v-if="status === 'uploading'"
      class="absolute inset-0 flex items-center justify-center bg-black/50 rounded-lg"
    >
      <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-white" />
    </div>

    <UTooltip v-if="status === 'error'" :text="error">
      <div class="absolute inset-0 flex items-center justify-center bg-error/50 rounded-lg">
        <UIcon name="i-lucide-alert-circle" class="size-8 text-white" />
      </div>
    </UTooltip>

    <UButton
      v-if="removable && status !== 'uploading'"
      icon="i-lucide-x"
      size="xs"
      square
      color="neutral"
      variant="solid"
      class="absolute p-0 -top-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity rounded-full"
      @click.stop="emit('remove')"
    />

    <!-- Hidden audio player -->
    <audio
      v-if="isAudio && previewUrl"
      ref="audioRef"
      :src="previewUrl"
      class="hidden"
      @ended="handleMediaEnded"
    />

    <!-- Hidden video (for audio-only playback) -->
    <video
      v-if="isVideo && previewUrl"
      ref="videoRef"
      :src="previewUrl"
      class="hidden"
      @ended="handleMediaEnded"
    />

    <!-- Image lightbox -->
    <ImageLightbox
      v-if="showLightbox && isImage && previewUrl"
      :src="previewUrl"
      :alt="name"
      @close="showLightbox = false"
    />
  </div>
</template>
