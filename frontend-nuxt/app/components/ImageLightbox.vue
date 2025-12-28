<script setup lang="ts">
const props = defineProps<{
  src: string
  alt?: string
}>()

const emit = defineEmits<{
  close: []
}>()

// Handle escape key
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    emit('close')
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-[100] bg-black/90 flex items-center justify-center p-4 backdrop-blur-sm"
      @click="emit('close')"
    >
      <!-- Close button -->
      <UButton
        icon="i-lucide-x"
        color="white"
        variant="ghost"
        size="xl"
        class="absolute top-4 right-4 z-10"
        @click="emit('close')"
      />

      <!-- Image -->
      <img
        :src="src"
        :alt="alt || 'Image preview'"
        class="max-w-full max-h-full object-contain rounded-lg shadow-2xl"
        @click.stop
      />

      <!-- Optional filename -->
      <div v-if="alt" class="absolute bottom-4 left-1/2 -translate-x-1/2 text-white/80 text-sm bg-black/50 px-4 py-2 rounded-full">
        {{ alt }}
      </div>
    </div>
  </Teleport>
</template>
