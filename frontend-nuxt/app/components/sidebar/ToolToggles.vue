<script setup lang="ts">
// Tool definitions with Spanish labels
const TOOLS = [
  { id: 'search_orders', label: 'Buscar Órdenes', description: 'Buscar órdenes por paciente o cédula', icon: 'i-lucide-search' },
  { id: 'get_order_results', label: 'Ver Resultados', description: 'Obtener resultados de una orden', icon: 'i-lucide-file-text' },
  { id: 'get_order_info', label: 'Info de Orden', description: 'Ver información de una orden', icon: 'i-lucide-info' },
  { id: 'edit_results', label: 'Editar Resultados', description: 'Modificar campos de resultados', icon: 'i-lucide-edit' },
  { id: 'edit_order_exams', label: 'Editar Exámenes', description: 'Agregar/quitar exámenes de orden', icon: 'i-lucide-list-plus' },
  { id: 'create_new_order', label: 'Nueva Orden', description: 'Crear orden o cotización', icon: 'i-lucide-plus-circle' },
  { id: 'get_available_exams', label: 'Lista Exámenes', description: 'Ver exámenes disponibles', icon: 'i-lucide-list' },
  { id: 'ask_user', label: 'Preguntar', description: 'Pedir aclaración al usuario', icon: 'i-lucide-message-circle' },
] as const

const props = defineProps<{
  modelValue: string[]
  collapsed?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [tools: string[]]
}>()

function toggleTool(toolId: string, enabled: boolean) {
  if (enabled) {
    emit('update:modelValue', [...props.modelValue, toolId])
  } else {
    emit('update:modelValue', props.modelValue.filter(t => t !== toolId))
  }
}

function enableAll() {
  emit('update:modelValue', TOOLS.map(t => t.id))
}

function disableAll() {
  emit('update:modelValue', [])
}
</script>

<template>
  <div v-if="collapsed" class="p-2">
    <div class="text-xs text-muted">
      Herramientas: {{ modelValue.length }}/{{ TOOLS.length }}
    </div>
  </div>
  <div v-else class="p-3 space-y-3">
    <h3 class="font-semibold text-sm">Herramientas</h3>
    <div class="space-y-2">
      <div
        v-for="tool in TOOLS"
        :key="tool.id"
        class="flex items-center justify-between gap-2"
      >
        <label
          :for="`tool-${tool.id}`"
          class="text-xs cursor-pointer flex-1 flex items-center gap-1.5"
          :title="tool.description"
        >
          <UIcon :name="tool.icon" class="w-3.5 h-3.5 text-muted" />
          {{ tool.label }}
        </label>
        <USwitch
          :id="`tool-${tool.id}`"
          :model-value="modelValue.includes(tool.id)"
          size="xs"
          @update:model-value="toggleTool(tool.id, $event)"
        />
      </div>
    </div>
    <div class="pt-2 border-t border-default flex gap-2">
      <button
        class="text-xs text-muted hover:text-default"
        @click="enableAll"
      >
        Todas
      </button>
      <button
        class="text-xs text-muted hover:text-default"
        @click="disableAll"
      >
        Ninguna
      </button>
    </div>
  </div>
</template>
