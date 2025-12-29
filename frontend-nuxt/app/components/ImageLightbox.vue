<script setup lang="ts">
/**
 * Image lightbox component for viewing images in full screen.
 */
const props = defineProps<{
  src: string
  alt?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const scale = ref(1)
const position = ref({ x: 0, y: 0 })
const isDragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })

function handleWheel(e: WheelEvent) {
  e.preventDefault()
  const delta = e.deltaY > 0 ? -0.1 : 0.1
  scale.value = Math.max(0.5, Math.min(3, scale.value + delta))
}

function handleMouseDown(e: MouseEvent) {
  if (scale.value > 1) {
    isDragging.value = true
    dragStart.value = {
      x: e.clientX - position.value.x,
      y: e.clientY - position.value.y
    }
  }
}

function handleMouseMove(e: MouseEvent) {
  if (isDragging.value) {
    position.value = {
      x: e.clientX - dragStart.value.x,
      y: e.clientY - dragStart.value.y
    }
  }
}

function handleMouseUp() {
  isDragging.value = false
}

function resetView() {
  scale.value = 1
  position.value = { x: 0, y: 0 }
}

function close() {
  emit('close')
}

// Handle escape key
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    close()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  document.body.style.overflow = 'hidden'
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
      @click.self="close"
      @wheel="handleWheel"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseUp"
    >
      <!-- Controls -->
      <div class="absolute top-4 right-4 flex items-center gap-2 z-10">
        <UButton
          icon="i-lucide-zoom-out"
          color="white"
          variant="ghost"
          size="lg"
          :disabled="scale <= 0.5"
          @click="scale = Math.max(0.5, scale - 0.25)"
        />
        <UButton
          icon="i-lucide-zoom-in"
          color="white"
          variant="ghost"
          size="lg"
          :disabled="scale >= 3"
          @click="scale = Math.min(3, scale + 0.25)"
        />
        <UButton
          icon="i-lucide-maximize-2"
          color="white"
          variant="ghost"
          size="lg"
          @click="resetView"
        />
        <UButton
          icon="i-lucide-x"
          color="white"
          variant="ghost"
          size="lg"
          @click="close"
        />
      </div>

      <!-- Image -->
      <img
        :src="props.src"
        :alt="props.alt || 'Image'"
        class="max-w-full max-h-full object-contain select-none transition-transform"
        :class="{ 'cursor-grab': scale > 1, 'cursor-grabbing': isDragging }"
        :style="{
          transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
          transitionDuration: isDragging ? '0ms' : '150ms'
        }"
        draggable="false"
      />

      <!-- Zoom indicator -->
      <div
        v-if="scale !== 1"
        class="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/50 text-white px-3 py-1 rounded-full text-sm"
      >
        {{ Math.round(scale * 100) }}%
      </div>
    </div>
  </Teleport>
</template>
