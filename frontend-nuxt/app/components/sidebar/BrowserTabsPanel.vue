<script setup lang="ts">
interface TabState {
  exams?: string[]
  total?: string
  examenes_count?: number
  field_values?: Record<string, string>
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
  collapsed?: boolean
}>()

const emit = defineEmits<{
  openEditor: []
  refresh: []
}>()

const tabs = ref<TabInfo[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const lastUpdate = ref<Date | null>(null)

const TAB_TYPE_LABELS: Record<string, { label: string; icon: string }> = {
  ordenes_list: { label: 'Lista', icon: 'i-lucide-list' },
  nueva_orden: { label: 'Nueva Orden', icon: 'i-lucide-plus' },
  orden_edit: { label: 'Editar Orden', icon: 'i-lucide-edit' },
  resultados: { label: 'Resultados', icon: 'i-lucide-flask-conical' },
  login: { label: 'Login', icon: 'i-lucide-lock' },
  unknown: { label: 'Otra', icon: 'i-lucide-help-circle' },
}

const TAB_TYPE_COLORS: Record<string, string> = {
  ordenes_list: 'bg-blue-500/10 border-blue-500/30',
  nueva_orden: 'bg-green-500/10 border-green-500/30',
  orden_edit: 'bg-yellow-500/10 border-yellow-500/30',
  resultados: 'bg-purple-500/10 border-purple-500/30',
  login: 'bg-orange-500/10 border-orange-500/30',
  unknown: 'bg-gray-500/10 border-gray-500/30',
}

async function fetchTabs(isInitial = false) {
  try {
    if (isInitial) loading.value = true
    error.value = null

    const config = useRuntimeConfig()
    const backendUrl = config.public?.backendUrl || 'http://localhost:8000'

    const response = await fetch(`${backendUrl}/api/browser/tabs/detailed`)
    if (!response.ok) throw new Error('Failed to fetch tabs')

    const data = await response.json()
    tabs.value = data.tabs || []
    lastUpdate.value = new Date()
  } catch {
    if (isInitial) {
      error.value = 'Backend no disponible'
      tabs.value = []
    }
  } finally {
    if (isInitial) loading.value = false
  }
}

function handleRefresh() {
  fetchTabs(true)
  emit('refresh')
}

// Auto-refresh every 10 seconds when visible and not collapsed
let interval: ReturnType<typeof setInterval> | null = null

function startPolling() {
  if (interval) clearInterval(interval)
  interval = setInterval(() => {
    if (document.visibilityState === 'visible' && !props.collapsed) {
      fetchTabs(false)
    }
  }, 10000)
}

function handleVisibilityChange() {
  if (document.visibilityState === 'visible' && !props.collapsed) {
    fetchTabs(false)
    startPolling()
  } else if (interval) {
    clearInterval(interval)
    interval = null
  }
}

onMounted(() => {
  fetchTabs(true)
  if (!props.collapsed) {
    startPolling()
    document.addEventListener('visibilitychange', handleVisibilityChange)
  }
})

onUnmounted(() => {
  if (interval) clearInterval(interval)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

watch(() => props.collapsed, (collapsed) => {
  if (collapsed && interval) {
    clearInterval(interval)
    interval = null
  } else if (!collapsed) {
    fetchTabs(false)
    startPolling()
  }
})
</script>

<template>
  <div v-if="collapsed" class="p-2">
    <div class="text-xs text-muted">
      Tabs: {{ tabs.length }}
    </div>
  </div>
  <div v-else class="p-3 space-y-3">
    <div class="flex items-center justify-between">
      <h3 class="font-semibold text-sm">Pestañas del Navegador</h3>
      <div class="flex gap-1">
        <UButton
          v-if="tabs.length > 0"
          icon="i-lucide-edit"
          variant="ghost"
          size="xs"
          title="Editar pestañas"
          @click="emit('openEditor')"
        />
        <UButton
          icon="i-lucide-refresh-cw"
          variant="ghost"
          size="xs"
          :loading="loading"
          @click="handleRefresh"
        />
      </div>
    </div>

    <div v-if="error" class="text-xs text-error">
      {{ error }}
    </div>

    <div class="max-h-[200px] overflow-y-auto space-y-2">
      <div
        v-if="tabs.length === 0 && !loading"
        class="text-xs text-muted text-center py-4"
      >
        No hay pestañas abiertas
      </div>

      <div
        v-if="loading && tabs.length === 0"
        class="text-xs text-muted text-center py-4"
      >
        Cargando...
      </div>

      <div
        v-for="(tab, idx) in tabs"
        :key="`${tab.type}-${tab.id || idx}`"
        class="p-2 border rounded"
        :class="[
          TAB_TYPE_COLORS[tab.type] || TAB_TYPE_COLORS.unknown,
          tab.active ? 'ring-2 ring-primary' : ''
        ]"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-1">
              <UIcon
                :name="TAB_TYPE_LABELS[tab.type]?.icon || 'i-lucide-help-circle'"
                class="w-3.5 h-3.5"
              />
              <span class="text-xs font-medium">
                {{ TAB_TYPE_LABELS[tab.type]?.label || tab.type }}
              </span>
              <UBadge
                v-if="tab.is_new"
                size="xs"
                color="success"
                variant="solid"
              >
                NUEVA
              </UBadge>
              <UBadge
                v-if="tab.active"
                size="xs"
                color="primary"
                variant="solid"
              >
                ACTIVA
              </UBadge>
            </div>

            <div v-if="tab.id" class="text-[10px] text-muted">
              {{ tab.type === 'resultados' ? `#${tab.id}` : `ID: ${tab.id}` }}
              <span v-if="tab.instance && tab.instance > 1">({{ tab.instance }})</span>
            </div>

            <div
              v-if="tab.paciente"
              class="text-xs truncate"
              :title="tab.paciente"
            >
              {{ tab.paciente }}
            </div>

            <!-- Show state for new tabs -->
            <div v-if="tab.is_new && tab.state" class="mt-1 text-[10px] text-muted">
              <div v-if="tab.state.exams && tab.state.exams.length > 0">
                Exámenes: {{ tab.state.exams.slice(0, 3).join(', ') }}{{ tab.state.exams.length > 3 ? '...' : '' }}
              </div>
              <div v-if="tab.state.examenes_count !== undefined">
                Exámenes: {{ tab.state.examenes_count }}
              </div>
              <div v-if="tab.state.total">
                Total: ${{ tab.state.total }}
              </div>
            </div>

            <!-- Show changes for known tabs -->
            <div
              v-if="!tab.is_new && tab.changes && Object.keys(tab.changes).length > 0"
              class="mt-1 text-[10px] text-warning"
            >
              <div class="font-medium">Cambios:</div>
              <div v-if="tab.changes.exams">
                Exámenes: {{ tab.changes.exams.slice(0, 3).join(', ') }}
              </div>
              <div v-if="tab.changes.total">
                Total: ${{ tab.changes.total }}
              </div>
              <div v-if="tab.changes.field_values">
                {{ Object.keys(tab.changes.field_values).length }} campos
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="lastUpdate" class="text-[10px] text-muted text-right">
      Actualizado: {{ lastUpdate.toLocaleTimeString() }}
    </div>
  </div>
</template>
