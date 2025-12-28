<script setup lang="ts">
const props = defineProps<{
  fileName: string
  rotation: number
  originalUrl?: string
  rotatedUrl: string
  model?: string | null
  timing?: { modelMs?: number; totalMs?: number }
}>()

const emit = defineEmits<{
  'click-image': [url: string]
}>()

// Format timing info
const timingText = computed(() => {
  if (!props.timing) return ''
  const parts: string[] = []
  if (props.timing.modelMs) parts.push(`${props.timing.modelMs}ms`)
  if (props.timing.totalMs) parts.push(`total: ${props.timing.totalMs}ms`)
  return parts.join(', ')
})
</script>

<template>
  <div class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 my-2 border border-gray-200 dark:border-gray-700">
    <div class="flex-shrink-0 mt-0.5">
      <UIcon
        name="i-lucide-rotate-cw"
        class="w-5 h-5"
        style="color: var(--ui-success)"
      />
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="font-medium text-sm text-gray-900 dark:text-gray-100">
          Imagen rotada automáticamente
        </span>
        <UBadge
          color="success"
          size="xs"
          variant="subtle"
        >
          {{ rotation }}° aplicado
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

      <!-- Rotated image thumbnail -->
      <div class="mt-3">
        <div class="text-xs text-gray-500 dark:text-gray-500 mb-1">Resultado:</div>
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
