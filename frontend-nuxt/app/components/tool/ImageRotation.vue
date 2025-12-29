<script setup lang="ts">
import type { RotationResult } from '~/composables/useImageRotation'

const props = defineProps<{
  rotationState: RotationResult
}>()

const isRunning = computed(() =>
  props.rotationState.status === 'pending' || props.rotationState.status === 'processing'
)

const isCompleted = computed(() => props.rotationState.status === 'completed')
const isError = computed(() => props.rotationState.status === 'error')

const rotationLabel = computed(() => {
  if (props.rotationState.rotation === 0) return 'Sin rotación necesaria'
  if (props.rotationState.rotation === 90) return 'Rotado 90° horario'
  if (props.rotationState.rotation === 180) return 'Rotado 180°'
  if (props.rotationState.rotation === 270) return 'Rotado 90° antihorario'
  return `Rotado ${props.rotationState.rotation}°`
})
</script>

<template>
  <div class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 my-2 border border-gray-200 dark:border-gray-700">
    <div class="flex-shrink-0 mt-0.5">
      <UIcon
        :name="isRunning ? 'i-lucide-loader-2' : 'i-lucide-rotate-cw'"
        :class="{ 'animate-spin': isRunning }"
        class="w-5 h-5"
        :style="{ color: isError ? 'var(--ui-error)' : isCompleted ? 'var(--ui-success)' : 'var(--ui-primary)' }"
      />
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="font-medium text-sm text-gray-900 dark:text-gray-100">
          {{ isRunning ? 'Detectando orientación...' : 'Detección de orientación' }}
        </span>
        <UBadge
          :color="isCompleted ? 'success' : isError ? 'error' : 'info'"
          size="xs"
          variant="subtle"
        >
          {{ isRunning ? 'En progreso' : isCompleted ? 'Completado' : isError ? 'Error' : rotationState.status }}
        </UBadge>
      </div>

      <!-- Show file name -->
      <div class="mt-2 text-xs text-gray-600 dark:text-gray-400 flex gap-2">
        <span class="font-mono text-gray-500 dark:text-gray-500 shrink-0">imagen:</span>
        <span class="truncate">{{ rotationState.fileName }}</span>
      </div>

      <!-- Show result if completed -->
      <div v-if="isCompleted" class="mt-2 text-xs text-gray-500 dark:text-gray-400">
        <span class="font-medium">Resultado:</span>
        <span class="ml-1">{{ rotationLabel }}</span>
      </div>

      <!-- Show error if failed -->
      <div v-if="isError" class="mt-2 text-xs text-red-500 dark:text-red-400">
        <span class="font-medium">Error:</span>
        <span class="ml-1">{{ rotationState.error || 'Detección fallida' }}</span>
      </div>
    </div>
  </div>
</template>
