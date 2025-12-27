<script setup lang="ts">
const { loggedIn } = useUserSession()
const { isOAuthEnabled } = useAuthConfig()

// Allow uploads if: user is logged in OR OAuth is not configured (local dev)
const canUpload = computed(() => loggedIn.value || !isOAuthEnabled.value)

const emit = defineEmits<{
  filesSelected: [files: File[]]
}>()

const inputId = useId()

function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])

  if (files.length > 0) {
    emit('filesSelected', files)
  }

  input.value = ''
}
</script>

<template>
  <UTooltip
    :content="{
      side: 'top'
    }"
    :text="!canUpload ? 'Debes iniciar sesión para subir archivos' : ''"
  >
    <label :for="inputId" :class="{ 'cursor-not-allowed opacity-50': !canUpload }">
      <UButton
        icon="i-lucide-paperclip"
        variant="ghost"
        color="neutral"
        size="sm"
        as="span"
        :disabled="!canUpload"
      />
    </label>
    <input
      :id="inputId"
      type="file"
      multiple
      :accept="FILE_UPLOAD_CONFIG.acceptPattern"
      class="hidden"
      :disabled="!canUpload"
      @change="handleFileSelect"
    >
  </UTooltip>
</template>
