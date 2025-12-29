<script setup lang="ts">
const props = defineProps<{
  fileName: string
  rotation: number
  originalUrl?: string
  rotatedUrl: string
  model?: string | null
  timing?: { modelMs?: number; totalMs?: number }
  state?: 'pending' | 'running' | 'completed'
}>()

const emit = defineEmits<{
  'click-image': [url: string]
}>()

// Only show if image was actually rotated (rotation != 0)
const wasRotated = computed(() => props.rotation !== 0)

// Format timing info
const timingText = computed(() => {
  if (!props.timing) return ''
  const parts: string[] = []
  if (props.timing.modelMs) parts.push(`${props.timing.modelMs}ms`)
  if (props.timing.totalMs) parts.push(`total: ${props.timing.totalMs}ms`)
  return parts.join(', ')
})

// State display
const stateText = computed(() => {
  switch (props.state) {
    case 'pending': return 'Analizando...'
    case 'running': return 'Rotando...'
    case 'completed': return wasRotated.value ? '✓ Completado' : '✓ No requiere rotación'
    default: return wasRotated.value ? '✓ Completado' : '✓ No requiere rotación'
  }
})

const stateColor = computed(() => {
  if (props.state === 'pending' || props.state === 'running') return 'info'
  return wasRotated.value ? 'success' : 'neutral'
})
</script>

<template>
  <div class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 my-2 border border-gray-200 dark:border-gray-700">
    <div class="flex-shrink-0 mt-0.5">
      <UIcon
        :name="state === 'running' || state === 'pending' ? 'i-lucide-loader-2' : 'i-lucide-rotate-cw'"
        :class="{ 'animate-spin': state === 'running' || state === 'pending' }"
        class="w-5 h-5"
        :style="wasRotated ? 'color: var(--ui-success)' : 'color: var(--ui-text-muted)'"
      />
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="font-medium text-sm text-gray-900 dark:text-gray-100">
          Detección de rotación
        </span>
        <UBadge
          :color="stateColor"
          size="xs"
          variant="subtle"
        >
          {{ wasRotated ? `${rotation}° aplicado` : stateText }}
        </UBadge>
      </div>

      <!-- Show details -->
      <div class="mt-2 space-y-1 text-xs text-gray-600 dark:text-gray-400">
        <div class="flex gap-2">
          <span class="font-mono text-gray-500 dark:text-gray-500 shrink-0">archivo:</span>
          <span class="truncate">{{ fileName }}</span>
        </div>
        <div v-if="model" class="flex gap-2">
          <span class="font-mono text-gray-500 dark:text-gray-500 shrink-0">modelo:</span>
          <span class="truncate">{{ model }}</span>
        </div>
        <div v-if="timingText" class="flex gap-2">
          <span class="font-mono text-gray-500 dark:text-gray-500 shrink-0">tiempo:</span>
          <span>{{ timingText }}</span>
        </div>
      </div>

      <!-- Only show rotated image thumbnail if rotation was applied -->
      <div v-if="wasRotated && rotatedUrl" class="mt-3">
        <div class="text-xs text-gray-500 dark:text-gray-500 mb-1">Imagen rotada:</div>
        <div
          class="inline-block cursor-pointer hover:ring-2 hover:ring-primary rounded-lg transition-all"
          @click="emit('click-image', rotatedUrl)"
        >
          <img
            :src="rotatedUrl"
            :alt="`${fileName} rotado ${rotation}°`"
            class="max-w-[120px] max-h-[120px] rounded-lg border border-default object-cover"
          />
        </div>
      </div>
    </div>
  </div>
</template>
