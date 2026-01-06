<script setup lang="ts">
const props = defineProps<{
  name: string
  args: Record<string, unknown>
  groupedArgs?: Array<Record<string, unknown>>  // For grouped consecutive tools
  result?: unknown
  state: 'pending' | 'partial-call' | 'call' | 'result' | 'error'
}>()

const emit = defineEmits<{
  optionClick: [option: string]
}>()

// Check if this is a grouped tool display
const isGrouped = computed(() => props.groupedArgs && props.groupedArgs.length > 1)
const groupCount = computed(() => props.groupedArgs?.length || 1)

// Map tool names to display names and icons
const toolInfo: Record<string, { label: string; icon: string; activeLabel: string }> = {
  search_orders: {
    label: 'Buscar órdenes',
    activeLabel: 'Buscando órdenes...',
    icon: 'i-lucide-search'
  },
  get_order_results: {
    label: 'Obtener resultados',
    activeLabel: 'Obteniendo resultados...',
    icon: 'i-lucide-file-text'
  },
  get_order_info: {
    label: 'Información de orden',
    activeLabel: 'Obteniendo información...',
    icon: 'i-lucide-info'
  },
  edit_results: {
    label: 'Editar resultados',
    activeLabel: 'Editando resultados...',
    icon: 'i-lucide-edit'
  },
  edit_order_exams: {
    label: 'Editar exámenes',
    activeLabel: 'Editando exámenes...',
    icon: 'i-lucide-list-checks'
  },
  create_new_order: {
    label: 'Crear orden',
    activeLabel: 'Creando orden...',
    icon: 'i-lucide-plus-circle'
  },
  get_available_exams: {
    label: 'Exámenes disponibles',
    activeLabel: 'Obteniendo exámenes...',
    icon: 'i-lucide-list'
  },
  ask_user: {
    label: 'Pregunta al usuario',
    activeLabel: 'Esperando respuesta...',
    icon: 'i-lucide-message-circle'
  },
  'image-rotation': {
    label: 'Corrección de orientación',
    activeLabel: 'Corrigiendo orientación de imágenes...',
    icon: 'i-lucide-rotate-cw'
  },
  'image-preprocessing': {
    label: 'Preprocesamiento de imágenes',
    activeLabel: 'Preprocesando imágenes...',
    icon: 'i-lucide-image-plus'
  },
  'document-segmentation': {
    label: 'Segmentación de documento',
    activeLabel: 'Segmentando documento...',
    icon: 'i-lucide-crop'
  }
}

const info = computed(() => toolInfo[props.name] || {
  label: props.name,
  activeLabel: `Ejecutando ${props.name}...`,
  icon: 'i-lucide-wrench'
})

const isRunning = computed(() =>
  props.state === 'pending' || props.state === 'partial-call' || props.state === 'call'
)

const isCompleted = computed(() => props.state === 'result')
const isError = computed(() => props.state === 'error')

// Extract ask_user options from result
const askUserOptions = computed(() => {
  if (props.name !== 'ask_user' || !props.result) return []
  const result = props.result as Record<string, unknown>
  if (Array.isArray(result.options)) {
    return result.options as string[]
  }
  return []
})

const askUserMessage = computed(() => {
  if (props.name !== 'ask_user' || !props.result) return ''
  const result = props.result as Record<string, unknown>
  return result.message as string || ''
})

function handleOptionClick(option: string) {
  emit('optionClick', option)
}

// Format argument value for display
function formatValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.join(', ')
  }
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value)
  }
  return String(value)
}

// Consolidated args for grouped tools - extract key param from each
const consolidatedArgs = computed(() => {
  if (!isGrouped.value || !props.groupedArgs) return null

  // For search_orders, consolidate 'search' params
  if (props.name === 'search_orders') {
    const searches = props.groupedArgs
      .map(a => a.search)
      .filter(s => s)
      .map(s => String(s))
    const display = searches.slice(0, 4).join(', ')
    const remaining = searches.length - 4
    return {
      search: remaining > 0 ? `${display}... (+${remaining} más)` : display
    }
  }

  // For get_order_results, consolidate 'order_nums' params
  if (props.name === 'get_order_results') {
    const allNums = props.groupedArgs
      .flatMap(a => a.order_nums as string[] || [])
    const display = allNums.slice(0, 6).join(', ')
    const remaining = allNums.length - 6
    return {
      order_nums: remaining > 0 ? `${display}... (+${remaining} más)` : display
    }
  }

  // Default: show count
  return { count: `${props.groupedArgs.length} llamadas` }
})

// Effective args to display (consolidated or regular)
const displayArgs = computed(() => {
  if (consolidatedArgs.value) return consolidatedArgs.value
  return props.args
})

// Format image-rotation result for display
interface RotationResultItem {
  name: string
  rotation: number
  applied: boolean
  thumbnailUrl?: string
  mediaType?: string
}

interface ImageRotationResult {
  processed?: number
  rotated?: number
  detected?: number
  results?: RotationResultItem[]
}

// Format image-preprocessing result for display
interface PreprocessingResultItem {
  name: string
  rotation: number
  useCrop: boolean
  hasCrop: boolean
  cropConfidence?: number
  thumbnailUrl?: string
  mediaType?: string
}

interface ImagePreprocessingResult {
  processed?: number
  rotated?: number
  cropped?: number
  timing?: {
    preprocessMs: number
    selectMs: number
    applyMs: number
    totalMs: number
  }
  results?: PreprocessingResultItem[]
}

// Extract rotated image thumbnails from image-rotation result
const rotatedThumbnails = computed(() => {
  if (props.name !== 'image-rotation' || !props.result) return []
  const result = props.result as ImageRotationResult
  if (!result.results) return []
  return result.results
    .filter(r => r.applied && r.thumbnailUrl)
    .map(r => ({
      name: r.name,
      url: r.thumbnailUrl!,
      rotation: r.rotation
    }))
})

// Extract processed image thumbnails from image-preprocessing result
const preprocessedThumbnails = computed(() => {
  if (props.name !== 'image-preprocessing' || !props.result) return []
  const result = props.result as ImagePreprocessingResult
  if (!result.results) return []
  return result.results
    .filter(r => r.thumbnailUrl)
    .map(r => ({
      name: r.name,
      url: r.thumbnailUrl!,
      rotation: r.rotation,
      cropped: r.useCrop
    }))
})

// Lightbox state for viewing rotated images
const lightboxImage = ref<{ url: string; name: string } | null>(null)

function showImageLightbox(url: string, name: string) {
  lightboxImage.value = { url, name }
}

function formatRotationResult(result: ImageRotationResult): string {
  if (!result.results || result.results.length === 0) {
    return 'Sin imágenes procesadas'
  }

  const descriptions = result.results.map(r => {
    if (r.rotation === 0) {
      return `${r.name}: sin rotación necesaria`
    }
    const status = r.applied ? 'corregida' : 'detectada'
    return `${r.name}: ${r.rotation}° (${status})`
  })

  return descriptions.join('; ')
}

function formatPreprocessingResult(result: ImagePreprocessingResult): string {
  // Show detailed AI decisions for each image
  if (result.results && result.results.length > 0) {
    const details = result.results.map((r, i) => {
      const parts: string[] = []
      if (r.rotation !== 0) {
        parts.push(`${r.rotation}°`)
      }
      if (r.useCrop) {
        parts.push('recortada')
      }
      if (parts.length === 0) {
        parts.push('sin cambios')
      }
      return `Img${i + 1}: ${parts.join(', ')}`
    })

    const timing = result.timing?.totalMs ? ` (${result.timing.totalMs}ms)` : ''
    return details.join(' | ') + timing
  }

  // Fallback to simple counts
  const parts: string[] = []
  if (result.processed) {
    parts.push(`${result.processed} imagen${result.processed > 1 ? 'es' : ''}`)
  }
  if (result.timing?.totalMs) {
    parts.push(`${result.timing.totalMs}ms`)
  }

  return parts.join(', ') || 'Procesamiento completado'
}

// Format any tool result for display
function formatResult(toolName: string, result: unknown): string {
  if (typeof result === 'string') {
    return result.length > 100 ? result.slice(0, 100) + '...' : result
  }

  if (toolName === 'image-rotation' && typeof result === 'object' && result !== null) {
    return formatRotationResult(result as ImageRotationResult)
  }

  if (toolName === 'image-preprocessing' && typeof result === 'object' && result !== null) {
    return formatPreprocessingResult(result as ImagePreprocessingResult)
  }

  // For other object results, show a summary
  if (typeof result === 'object' && result !== null) {
    const obj = result as Record<string, unknown>
    // Try to extract meaningful info
    if ('count' in obj) return `${obj.count} resultados`
    if ('total' in obj) return `Total: ${obj.total}`
    if ('message' in obj) return String(obj.message)
    return 'Ver respuesta del asistente'
  }

  return String(result)
}

</script>

<template>
  <div class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 my-2 border border-gray-200 dark:border-gray-700">
    <div class="flex-shrink-0 mt-0.5">
      <UIcon
        :name="isRunning ? 'i-lucide-loader-2' : info.icon"
        :class="{ 'animate-spin': isRunning }"
        class="w-5 h-5"
        :style="{ color: isError ? 'var(--ui-error)' : isCompleted ? 'var(--ui-success)' : 'var(--ui-primary)' }"
      />
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="font-medium text-sm text-gray-900 dark:text-gray-100">
          {{ isRunning ? info.activeLabel : info.label }}
        </span>
        <UBadge
          :color="isCompleted ? 'success' : isError ? 'error' : 'info'"
          size="xs"
          variant="subtle"
        >
          {{ isRunning ? 'En progreso' : isCompleted ? 'Completado' : isError ? 'Error' : state }}
        </UBadge>
        <!-- Show count badge for grouped tools -->
        <UBadge
          v-if="isGrouped"
          color="neutral"
          size="xs"
          variant="subtle"
        >
          x{{ groupCount }}
        </UBadge>
      </div>

      <!-- Show tool arguments (consolidated for grouped tools) -->
      <div v-if="Object.keys(displayArgs).length > 0" class="mt-2 space-y-1">
        <div
          v-for="(value, key) in displayArgs"
          :key="key"
          class="text-xs text-gray-600 dark:text-gray-400 flex gap-2"
        >
          <span class="font-mono text-gray-500 dark:text-gray-500 shrink-0">{{ key }}:</span>
          <span class="truncate">{{ formatValue(value) }}</span>
        </div>
      </div>

      <!-- Show result summary if completed (but not for ask_user with options) -->
      <div v-if="isCompleted && result && !(name === 'ask_user' && askUserOptions.length > 0)" class="mt-2 text-xs text-gray-500 dark:text-gray-400">
        <span class="font-medium">Resultado:</span>
        <span class="ml-1">{{ formatResult(name, result) }}</span>
      </div>

      <!-- Ask user options as clickable buttons -->
      <div v-if="name === 'ask_user' && askUserOptions.length > 0 && isCompleted" class="mt-3 space-y-3">
        <p v-if="askUserMessage" class="text-base text-gray-700 dark:text-gray-300 font-medium">{{ askUserMessage }}</p>
        <div class="flex flex-wrap gap-3">
          <UButton
            v-for="(option, idx) in askUserOptions"
            :key="idx"
            color="primary"
            variant="soft"
            size="lg"
            class="text-base px-4 py-2"
            @click="handleOptionClick(option)"
          >
            {{ option }}
          </UButton>
        </div>
      </div>

      <!-- Show rotated image thumbnails for image-rotation tool -->
      <div v-if="rotatedThumbnails.length > 0" class="mt-3 flex flex-wrap gap-2">
        <div
          v-for="thumb in rotatedThumbnails"
          :key="thumb.name"
          class="relative group"
        >
          <img
            :src="thumb.url"
            :alt="thumb.name"
            class="w-20 h-20 object-cover rounded-lg border border-gray-200 dark:border-gray-600 cursor-pointer hover:opacity-80 transition-opacity"
            @click="showImageLightbox(thumb.url, thumb.name)"
          >
          <div class="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] px-1 py-0.5 rounded-b-lg text-center">
            {{ thumb.rotation }}° corregido
          </div>
        </div>
      </div>

      <!-- Show preprocessed image thumbnails for image-preprocessing tool -->
      <div v-if="preprocessedThumbnails.length > 0" class="mt-3 flex flex-wrap gap-2">
        <div
          v-for="thumb in preprocessedThumbnails"
          :key="thumb.name"
          class="relative group"
        >
          <img
            :src="thumb.url"
            :alt="thumb.name"
            class="w-20 h-20 object-cover rounded-lg border border-gray-200 dark:border-gray-600 cursor-pointer hover:opacity-80 transition-opacity"
            @click="showImageLightbox(thumb.url, thumb.name)"
          >
          <div class="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] px-1 py-0.5 rounded-b-lg text-center">
            <template v-if="thumb.rotation !== 0 && thumb.cropped">{{ thumb.rotation }}° + recorte</template>
            <template v-else-if="thumb.rotation !== 0">{{ thumb.rotation }}°</template>
            <template v-else-if="thumb.cropped">recortada</template>
            <template v-else>procesada</template>
          </div>
        </div>
      </div>

      <!-- Image lightbox for rotated images -->
      <ImageLightbox
        v-if="lightboxImage"
        :src="lightboxImage.url"
        :alt="lightboxImage.name"
        @close="lightboxImage = null"
      />
    </div>
  </div>
</template>
