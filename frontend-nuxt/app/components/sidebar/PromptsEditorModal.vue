<script setup lang="ts">
const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const { promptsConfig, fetchPrompts, savePrompts, fetchDefaultPrompts, isLoadingPrompts, isSavingPrompts } = useAdmin()
const toast = useToast()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})

// Local editable copy of prompts
const editablePrompts = ref<Record<string, string>>({})
const activeTab = ref('system_prompt')
const hasChanges = ref(false)
const isRestoringDefaults = ref(false)

// Fetch prompts when modal opens
watch(isOpen, async (open) => {
  if (open) {
    await fetchPrompts()
    if (promptsConfig.value?.prompts) {
      // Create a deep copy for editing
      editablePrompts.value = { ...promptsConfig.value.prompts }
      hasChanges.value = false
    }
  }
})

// Track changes
watch(editablePrompts, () => {
  if (promptsConfig.value?.prompts) {
    hasChanges.value = JSON.stringify(editablePrompts.value) !== JSON.stringify(promptsConfig.value.prompts)
  }
}, { deep: true })

async function handleSave() {
  try {
    await savePrompts(editablePrompts.value)
    hasChanges.value = false
    toast.add({
      title: 'Instrucciones guardadas',
      description: 'Los cambios se aplicarán en las nuevas conversaciones',
      icon: 'i-lucide-check-circle',
      color: 'primary'
    })
  } catch (error: any) {
    toast.add({
      title: 'Error al guardar',
      description: error.message || 'No se pudieron guardar los cambios',
      icon: 'i-lucide-alert-circle',
      color: 'error'
    })
  }
}

function handleReset() {
  if (promptsConfig.value?.prompts) {
    editablePrompts.value = { ...promptsConfig.value.prompts }
    hasChanges.value = false
  }
}

async function handleRestoreDefaults() {
  isRestoringDefaults.value = true
  try {
    const defaults = await fetchDefaultPrompts()
    if (defaults) {
      editablePrompts.value = { ...defaults }
      hasChanges.value = true
      toast.add({
        title: 'Valores predeterminados cargados',
        description: 'Haz clic en Guardar para aplicar los cambios',
        icon: 'i-lucide-undo-2',
        color: 'primary'
      })
    }
  } catch (error: any) {
    toast.add({
      title: 'Error',
      description: error.message || 'No se pudieron cargar los valores predeterminados',
      icon: 'i-lucide-alert-circle',
      color: 'error'
    })
  } finally {
    isRestoringDefaults.value = false
  }
}

// Get section info for display
function getSectionInfo(key: string) {
  return promptsConfig.value?.sections?.find(s => s.key === key) || {
    label: key,
    description: ''
  }
}
</script>

<template>
  <UModal v-model:open="isOpen" :ui="{ width: 'max-w-4xl' }">
    <template #content>
      <UCard class="h-[80vh] flex flex-col">
        <template #header>
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-lg font-semibold">Editar instrucciones para la IA</h3>
              <p class="text-sm text-muted mt-1">Configura cómo se comporta el asistente</p>
            </div>
            <div class="flex items-center gap-2">
              <UButton
                v-if="hasChanges"
                variant="ghost"
                color="neutral"
                size="sm"
                @click="handleReset"
              >
                Descartar
              </UButton>
              <UButton
                icon="i-lucide-save"
                size="sm"
                :loading="isSavingPrompts"
                :disabled="!hasChanges"
                @click="handleSave"
              >
                Guardar
              </UButton>
              <UButton
                icon="i-lucide-x"
                variant="ghost"
                color="neutral"
                size="sm"
                @click="isOpen = false"
              />
            </div>
          </div>
        </template>

        <div v-if="isLoadingPrompts" class="flex-1 flex items-center justify-center">
          <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-muted" />
        </div>

        <div v-else-if="promptsConfig" class="flex-1 flex flex-col min-h-0">
          <!-- Tab buttons -->
          <div class="flex gap-1 mb-4 flex-wrap">
            <UButton
              v-for="section in promptsConfig.sections"
              :key="section.key"
              :variant="activeTab === section.key ? 'soft' : 'ghost'"
              :color="activeTab === section.key ? 'primary' : 'neutral'"
              size="sm"
              @click="activeTab = section.key"
            >
              {{ section.label }}
            </UButton>
          </div>

          <!-- Active section editor -->
          <div class="flex-1 flex flex-col min-h-0">
            <div v-for="section in promptsConfig.sections" :key="section.key" class="flex-1 flex flex-col min-h-0">
              <template v-if="activeTab === section.key">
                <p class="text-sm text-muted mb-2">{{ section.description }}</p>
                <UTextarea
                  v-model="editablePrompts[section.key]"
                  :rows="15"
                  class="flex-1 font-mono text-sm"
                  :ui="{ base: 'min-h-[300px] resize-none' }"
                  placeholder="Escribe las instrucciones aquí..."
                />
              </template>
            </div>
          </div>

          <!-- Help text and restore button -->
          <div class="mt-4 p-3 bg-elevated rounded-lg">
            <div class="flex items-start justify-between gap-4">
              <div class="text-xs text-muted">
                <p class="font-medium mb-1">Consejos:</p>
                <ul class="list-disc list-inside space-y-1">
                  <li>Usa formato Markdown para estructurar las instrucciones</li>
                  <li>Los cambios se aplicarán en las <strong>nuevas conversaciones</strong></li>
                  <li>Las conversaciones existentes mantienen las instrucciones anteriores</li>
                </ul>
              </div>
              <UButton
                icon="i-lucide-undo-2"
                variant="outline"
                color="neutral"
                size="xs"
                :loading="isRestoringDefaults"
                @click="handleRestoreDefaults"
              >
                Restaurar valores predeterminados
              </UButton>
            </div>
          </div>
        </div>

        <div v-else class="flex-1 flex items-center justify-center text-muted">
          Error al cargar las instrucciones
        </div>
      </UCard>
    </template>
  </UModal>
</template>
