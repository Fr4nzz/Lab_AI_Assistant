<script setup lang="ts">
interface ExamDetail {
  codigo: string
  nombre: string
  valor: string | null
  estado: string | null
  can_remove: boolean
}

interface FieldDetail {
  key: string
  exam: string
  field: string
  value: string
  type: 'input' | 'select'
  options: string[] | null
  ref: string | null
}

interface TabState {
  paciente?: string
  order_num?: string
  exams?: string[]
  exams_details?: ExamDetail[]
  exams_count?: number
  examenes_count?: number
  total?: string
  field_values?: Record<string, string>
  fields_details?: FieldDetail[]
}

interface TabInfo {
  index: number
  type: 'ordenes_list' | 'nueva_orden' | 'orden_edit' | 'resultados' | 'login' | 'unknown'
  id: string | null
  paciente: string | null
  is_new: boolean
  active: boolean
  instance?: number
  state?: TabState
  changes?: Partial<TabState>
}

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const toast = useToast()

const tabs = ref<TabInfo[]>([])
const selectedTabIndex = ref<number | null>(null)
const loading = ref(true)
const executing = ref(false)
const error = ref<string | null>(null)

// Editable state
const editedExams = ref<string[]>([])
const editedExamsDetails = ref<ExamDetail[]>([])
const editedFields = ref<Record<string, string>>({})
const fieldsDetails = ref<FieldDetail[]>([])
const newExamCode = ref('')

const TAB_TYPE_LABELS: Record<string, string> = {
  ordenes_list: 'Lista de Órdenes',
  nueva_orden: 'Nueva Orden',
  orden_edit: 'Editar Orden',
  resultados: 'Resultados',
  login: 'Login',
  unknown: 'Otra',
}

const selectedTab = computed(() =>
  selectedTabIndex.value !== null ? tabs.value[selectedTabIndex.value] : null
)

async function fetchTabs() {
  try {
    loading.value = true
    error.value = null

    const config = useRuntimeConfig()
    const backendUrl = config.public?.backendUrl || 'http://localhost:8000'

    const response = await fetch(`${backendUrl}/api/browser/tabs/detailed`)
    if (!response.ok) throw new Error('Failed to fetch tabs')

    const data = await response.json()
    tabs.value = data.tabs || []
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error loading tabs'
  } finally {
    loading.value = false
  }
}

// When tab is selected, populate editable state
watch(selectedTabIndex, (index) => {
  if (index === null) {
    editedExams.value = []
    editedExamsDetails.value = []
    editedFields.value = {}
    fieldsDetails.value = []
    return
  }

  const tab = tabs.value[index]
  if (!tab) return

  const state = tab.state || {}
  editedExams.value = state.exams || []
  editedExamsDetails.value = state.exams_details || []
  editedFields.value = state.field_values || {}
  fieldsDetails.value = state.fields_details || []
})

// When modal opens, fetch tabs
watch(() => props.open, (open) => {
  if (open) {
    fetchTabs()
    selectedTabIndex.value = null
  }
})

function addExam() {
  const code = newExamCode.value.trim().toUpperCase()
  if (!code) return
  if (editedExams.value.includes(code)) {
    error.value = `El examen ${code} ya está en la lista`
    return
  }
  editedExams.value = [...editedExams.value, code]
  newExamCode.value = ''
  error.value = null
}

function removeExam(code: string) {
  editedExams.value = editedExams.value.filter(e => e !== code)
}

function restoreExam(code: string) {
  editedExams.value = [...editedExams.value, code]
}

function updateField(key: string, value: string) {
  editedFields.value = { ...editedFields.value, [key]: value }
}

async function executeToolCall(tool: string, args: Record<string, unknown>) {
  try {
    executing.value = true
    error.value = null

    const config = useRuntimeConfig()
    const backendUrl = config.public?.backendUrl || 'http://localhost:8000'

    const response = await fetch(`${backendUrl}/api/tools/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool, args }),
    })

    const result = await response.json()
    if (!response.ok) {
      throw new Error(result.error || 'Tool execution failed')
    }

    toast.add({
      title: 'Cambios aplicados',
      description: result.message || 'Los cambios se han guardado correctamente',
      icon: 'i-lucide-check-circle',
      color: 'success'
    })

    await fetchTabs()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error executing tool'
    toast.add({
      title: 'Error',
      description: error.value,
      icon: 'i-lucide-alert-circle',
      color: 'error'
    })
  } finally {
    executing.value = false
  }
}

async function applyExamChanges() {
  if (!selectedTab.value || !selectedTab.value.id) return

  const originalExams = selectedTab.value.state?.exams || []
  const toAdd = editedExams.value.filter(e => !originalExams.includes(e))
  const toRemove = originalExams.filter(e => !editedExams.value.includes(e))

  if (toAdd.length === 0 && toRemove.length === 0) {
    error.value = 'No hay cambios que aplicar'
    return
  }

  await executeToolCall('edit_order_exams', {
    order_id: selectedTab.value.id,
    add: toAdd.length > 0 ? toAdd : undefined,
    remove: toRemove.length > 0 ? toRemove : undefined,
  })
}

async function applyFieldChanges() {
  if (!selectedTab.value || !selectedTab.value.id) return

  const originalFields = selectedTab.value.state?.field_values || {}
  const changes: Array<{ orden: string; e: string; f: string; v: string }> = []

  for (const [key, value] of Object.entries(editedFields.value)) {
    if (originalFields[key] !== value) {
      const parts = key.split(':')
      const examName = parts[0] || ''
      const fieldName = parts[1] || ''
      changes.push({
        orden: selectedTab.value.id!,
        e: examName,
        f: fieldName,
        v: value,
      })
    }
  }

  if (changes.length === 0) {
    error.value = 'No hay cambios que aplicar'
    return
  }

  await executeToolCall('edit_results', { data: changes })
}

function hasExamChanges() {
  if (!selectedTab.value?.state?.exams) return editedExams.value.length > 0
  const original = selectedTab.value.state.exams
  return editedExams.value.length !== original.length ||
    editedExams.value.some(e => !original.includes(e)) ||
    original.some(e => !editedExams.value.includes(e))
}

function hasFieldChanges() {
  if (!selectedTab.value?.state?.field_values) return false
  const original = selectedTab.value.state.field_values
  return Object.entries(editedFields.value).some(([k, v]) => original[k] !== v)
}

function resetChanges() {
  if (!selectedTab.value) return
  editedExams.value = selectedTab.value.state?.exams || []
  editedExamsDetails.value = selectedTab.value.state?.exams_details || []
  editedFields.value = selectedTab.value.state?.field_values || {}
  fieldsDetails.value = selectedTab.value.state?.fields_details || []
  error.value = null
}

function close() {
  emit('update:open', false)
}
</script>

<template>
  <UModal :open="open" @update:open="emit('update:open', $event)" :ui="{ content: 'max-w-5xl' }">
    <template #content>
      <div class="flex h-[80vh]">
        <!-- Left panel - Tab list -->
        <div class="w-64 border-r border-default flex flex-col">
          <div class="p-3 border-b border-default flex items-center justify-between">
            <h2 class="font-semibold">Pestañas</h2>
            <UButton
              icon="i-lucide-refresh-cw"
              variant="ghost"
              size="xs"
              :loading="loading"
              @click="fetchTabs"
            />
          </div>

          <div class="flex-1 overflow-y-auto p-2 space-y-1">
            <div
              v-if="loading && tabs.length === 0"
              class="text-sm text-muted text-center py-4"
            >
              Cargando...
            </div>

            <button
              v-for="(tab, idx) in tabs"
              :key="idx"
              class="w-full text-left p-2 rounded text-sm hover:bg-muted/50"
              :class="[
                selectedTabIndex === idx ? 'bg-primary/10 ring-1 ring-primary' : '',
                tab.active ? 'font-semibold' : ''
              ]"
              @click="selectedTabIndex = idx"
            >
              <div class="flex items-center gap-1">
                <span>{{ TAB_TYPE_LABELS[tab.type] }}</span>
                <span v-if="tab.active" class="text-[10px] text-primary">●</span>
              </div>
              <div v-if="tab.id" class="text-[10px] text-muted">
                {{ tab.type === 'resultados' ? `#${tab.id}` : `ID: ${tab.id}` }}
              </div>
              <div v-if="tab.paciente" class="text-[10px] text-muted truncate">
                {{ tab.paciente }}
              </div>
            </button>
          </div>
        </div>

        <!-- Right panel - Tab details & editor -->
        <div class="flex-1 flex flex-col overflow-hidden">
          <div class="p-3 border-b border-default flex items-center justify-between shrink-0">
            <h2 class="font-semibold">
              {{ selectedTab ? TAB_TYPE_LABELS[selectedTab.type] : 'Selecciona una pestaña' }}
            </h2>
            <UButton
              icon="i-lucide-x"
              variant="ghost"
              size="xs"
              @click="close"
            />
          </div>

          <div class="flex-1 overflow-y-auto p-4">
            <!-- No tab selected -->
            <div v-if="!selectedTab" class="text-center text-muted py-8">
              Selecciona una pestaña para ver y editar sus datos
            </div>

            <!-- Results editor -->
            <div v-else-if="selectedTab.type === 'resultados'" class="space-y-4">
              <div class="text-sm text-muted">
                Paciente: <span class="font-medium text-default">{{ selectedTab.paciente || 'N/A' }}</span>
                |
                Orden: <span class="font-medium text-default">#{{ selectedTab.id }}</span>
              </div>

              <div class="space-y-2">
                <h3 class="font-medium text-sm">Campos de Resultados</h3>
                <div v-if="fieldsDetails.length > 0" class="border border-default rounded overflow-hidden">
                  <table class="w-full text-sm">
                    <thead class="bg-muted/50">
                      <tr>
                        <th class="text-left px-3 py-2 font-medium">Examen</th>
                        <th class="text-left px-3 py-2 font-medium">Campo</th>
                        <th class="text-left px-3 py-2 font-medium">Valor</th>
                        <th class="text-left px-3 py-2 font-medium text-muted">Ref.</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(field, idx) in fieldsDetails"
                        :key="field.key + idx"
                        class="border-t border-default"
                      >
                        <td class="px-3 py-2 text-xs text-muted">{{ field.exam }}</td>
                        <td class="px-3 py-2 text-xs font-medium">{{ field.field }}</td>
                        <td class="px-3 py-2">
                          <USelect
                            v-if="field.type === 'select' && field.options"
                            :model-value="editedFields[field.key] ?? field.value"
                            :items="field.options"
                            size="xs"
                            :class="editedFields[field.key] !== (selectedTab.state?.field_values?.[field.key] || '') ? 'ring-1 ring-warning' : ''"
                            @update:model-value="updateField(field.key, $event)"
                          />
                          <UInput
                            v-else
                            :model-value="editedFields[field.key] ?? field.value"
                            size="xs"
                            :class="editedFields[field.key] !== (selectedTab.state?.field_values?.[field.key] || '') ? 'ring-1 ring-warning' : ''"
                            @update:model-value="updateField(field.key, $event)"
                          />
                        </td>
                        <td class="px-3 py-2 text-xs text-muted">{{ field.ref || '-' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else class="text-sm text-muted py-4 text-center">
                  No hay campos de resultados disponibles
                </div>
              </div>
            </div>

            <!-- Order/exams editor -->
            <div v-else-if="selectedTab.type === 'orden_edit' || selectedTab.type === 'nueva_orden'" class="space-y-4">
              <div v-if="selectedTab.paciente" class="text-sm text-muted">
                Paciente: <span class="font-medium text-default">{{ selectedTab.paciente }}</span>
              </div>

              <div class="space-y-3">
                <h3 class="font-medium text-sm">Exámenes Agregados</h3>

                <div v-if="editedExamsDetails.length > 0" class="border border-default rounded overflow-hidden">
                  <table class="w-full text-sm">
                    <thead class="bg-muted/50">
                      <tr>
                        <th class="text-left px-3 py-2 font-medium">Código</th>
                        <th class="text-left px-3 py-2 font-medium">Nombre</th>
                        <th class="text-right px-3 py-2 font-medium">Precio</th>
                        <th class="w-10" />
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(exam, idx) in editedExamsDetails"
                        :key="exam.codigo + idx"
                        class="border-t border-default"
                        :class="!editedExams.includes(exam.codigo) ? 'bg-error/5 opacity-60' : ''"
                      >
                        <td
                          class="px-3 py-2 font-mono"
                          :class="!editedExams.includes(exam.codigo) ? 'line-through' : ''"
                        >
                          {{ exam.codigo }}
                        </td>
                        <td
                          class="px-3 py-2"
                          :class="!editedExams.includes(exam.codigo) ? 'line-through' : ''"
                        >
                          {{ exam.nombre }}
                        </td>
                        <td
                          class="px-3 py-2 text-right"
                          :class="!editedExams.includes(exam.codigo) ? 'line-through' : ''"
                        >
                          {{ exam.valor || '-' }}
                        </td>
                        <td class="px-2 py-2 text-center">
                          <UButton
                            v-if="!editedExams.includes(exam.codigo)"
                            icon="i-lucide-undo"
                            variant="ghost"
                            size="xs"
                            title="Restaurar"
                            @click="restoreExam(exam.codigo)"
                          />
                          <UButton
                            v-else
                            icon="i-lucide-x"
                            variant="ghost"
                            size="xs"
                            color="error"
                            title="Quitar"
                            @click="removeExam(exam.codigo)"
                          />
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else class="text-sm text-muted py-2">
                  No hay exámenes agregados
                </div>

                <!-- Total -->
                <div v-if="selectedTab.state?.total" class="flex justify-end text-sm font-medium pt-2 border-t border-default">
                  Total: <span class="ml-2">{{ selectedTab.state.total }}</span>
                </div>

                <!-- Add exam input -->
                <div class="pt-3 border-t border-default">
                  <h4 class="text-xs font-medium text-muted mb-2">Agregar Examen</h4>
                  <div class="flex gap-2">
                    <UInput
                      v-model="newExamCode"
                      placeholder="Código (ej: BH, EMO)"
                      size="sm"
                      class="flex-1"
                      @keydown.enter="addExam"
                    />
                    <UButton size="sm" @click="addExam">
                      Agregar
                    </UButton>
                  </div>
                </div>
              </div>
            </div>

            <!-- Non-editable tab -->
            <div v-else class="text-center text-muted py-8">
              Este tipo de pestaña no es editable
            </div>
          </div>

          <!-- Footer with action buttons -->
          <div
            v-if="selectedTab && (selectedTab.type === 'resultados' || selectedTab.type === 'orden_edit' || selectedTab.type === 'nueva_orden')"
            class="p-3 border-t border-default flex items-center justify-between shrink-0"
          >
            <div class="flex items-center gap-2">
              <span v-if="error" class="text-sm text-error">{{ error }}</span>
            </div>
            <div class="flex gap-2">
              <UButton
                variant="outline"
                @click="resetChanges"
              >
                Descartar
              </UButton>
              <UButton
                :loading="executing"
                :disabled="selectedTab.type === 'resultados' ? !hasFieldChanges() : !hasExamChanges()"
                @click="selectedTab.type === 'resultados' ? applyFieldChanges() : applyExamChanges()"
              >
                Aplicar Cambios
              </UButton>
            </div>
          </div>
        </div>
      </div>
    </template>
  </UModal>
</template>
