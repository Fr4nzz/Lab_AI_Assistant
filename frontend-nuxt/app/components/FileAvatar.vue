<script setup lang="ts">
interface FileAvatarProps {
  name: string
  type: string
  previewUrl?: string
  status?: 'idle' | 'uploading' | 'uploaded' | 'error' | 'processing'
  error?: string
  removable?: boolean
  clickable?: boolean
  rotation?: number // Rotation in degrees (0, 90, 180, 270)
}

const props = withDefaults(defineProps<FileAvatarProps>(), {
  status: 'idle',
  removable: false,
  clickable: true,
  rotation: 0
})

const emit = defineEmits<{
  remove: []
  click: []
}>()

const isImage = computed(() => props.type.startsWith('image/'))
const isAudio = computed(() => props.type.startsWith('audio/'))
const isVideo = computed(() => props.type.startsWith('video/'))
const wasRotated = computed(() => props.rotation !== 0 && props.rotation !== undefined)

function handleClick() {
  if (props.clickable && isImage.value && props.previewUrl) {
    emit('click')
  }
}
</script>

<template>
  <div class="relative group">
    <!-- Audio Player -->
    <template v-if="isAudio && previewUrl">
      <div class="flex items-center gap-2 bg-muted rounded-lg p-2 border border-default">
        <UIcon name="i-lucide-mic" class="w-5 h-5 text-muted shrink-0" />
        <audio controls class="h-8 max-w-[200px]">
          <source :src="previewUrl" :type="type" />
          Your browser does not support audio playback.
        </audio>
        <span class="text-xs text-muted truncate max-w-[80px]">{{ removeRandomSuffix(name) }}</span>
        <UButton
          v-if="removable && status !== 'uploading'"
          icon="i-lucide-x"
          size="xs"
          square
          color="neutral"
          variant="ghost"
          class="shrink-0"
          @click="emit('remove')"
        />
      </div>
    </template>

    <!-- Video Player -->
    <template v-else-if="isVideo && previewUrl">
      <div class="rounded-lg overflow-hidden bg-muted border border-default">
        <video controls class="max-w-[250px] max-h-[150px]">
          <source :src="previewUrl" :type="type" />
          Your browser does not support video playback.
        </video>
        <div class="flex items-center justify-between p-1">
          <span class="text-xs text-muted truncate max-w-[150px]">{{ removeRandomSuffix(name) }}</span>
          <UButton
            v-if="removable && status !== 'uploading'"
            icon="i-lucide-x"
            size="xs"
            square
            color="neutral"
            variant="ghost"
            @click="emit('remove')"
          />
        </div>
      </div>
    </template>

    <!-- Image / Other Files -->
    <template v-else>
      <UTooltip arrow :text="wasRotated ? `${removeRandomSuffix(name)} (rotado ${rotation}°)` : removeRandomSuffix(name)">
        <UAvatar
          size="3xl"
          :src="isImage ? previewUrl : undefined"
          :icon="getFileIcon(type, name)"
          class="border border-default rounded-lg"
          :class="{
            'opacity-50': status === 'uploading' || status === 'processing',
            'border-error': status === 'error',
            'cursor-pointer hover:ring-2 hover:ring-primary transition-all': clickable && isImage && previewUrl
          }"
          @click="handleClick"
        />
      </UTooltip>

      <!-- Processing/Uploading overlay -->
      <div
        v-if="status === 'uploading' || status === 'processing'"
        class="absolute inset-0 flex items-center justify-center bg-black/50 rounded-lg"
      >
        <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-white" />
      </div>

      <!-- Rotation badge -->
      <UTooltip v-if="wasRotated && status !== 'uploading' && status !== 'processing'" :text="`Rotado ${rotation}°`">
        <div class="absolute -bottom-1 -left-1 bg-info text-white text-[10px] font-bold px-1 py-0.5 rounded-full flex items-center gap-0.5">
          <UIcon name="i-lucide-rotate-cw" class="w-3 h-3" />
          {{ rotation }}°
        </div>
      </UTooltip>

      <UTooltip v-if="status === 'error'" :text="error">
        <div class="absolute inset-0 flex items-center justify-center bg-error/50 rounded-lg">
          <UIcon name="i-lucide-alert-circle" class="size-8 text-white" />
        </div>
      </UTooltip>

      <UButton
        v-if="removable && status !== 'uploading' && status !== 'processing'"
        icon="i-lucide-x"
        size="xs"
        square
        color="neutral"
        variant="solid"
        class="absolute p-0 -top-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity rounded-full"
        @click.stop="emit('remove')"
      />
    </template>
  </div>
</template>
