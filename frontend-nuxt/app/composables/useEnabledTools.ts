// All available tool IDs
export const ALL_TOOL_IDS = [
  'search_orders',
  'get_order_results',
  'get_order_info',
  'edit_results',
  'edit_order_exams',
  'create_new_order',
  'get_available_exams',
  'ask_user'
] as const

export type ToolId = typeof ALL_TOOL_IDS[number]

// Global state for enabled tools
export function useEnabledTools() {
  // Initialize with all tools enabled, persisted in localStorage
  const enabledTools = useState<string[]>('enabledTools', () => {
    if (import.meta.client) {
      const stored = localStorage.getItem('enabledTools')
      if (stored) {
        try {
          return JSON.parse(stored)
        } catch {
          // Invalid JSON, use defaults
        }
      }
    }
    return [...ALL_TOOL_IDS]
  })

  // Persist to localStorage when changed
  watch(enabledTools, (tools) => {
    if (import.meta.client) {
      localStorage.setItem('enabledTools', JSON.stringify(tools))
    }
  }, { deep: true })

  function enableAll() {
    enabledTools.value = [...ALL_TOOL_IDS]
  }

  function disableAll() {
    enabledTools.value = []
  }

  function toggle(toolId: string, enabled: boolean) {
    if (enabled) {
      if (!enabledTools.value.includes(toolId)) {
        enabledTools.value = [...enabledTools.value, toolId]
      }
    } else {
      enabledTools.value = enabledTools.value.filter(t => t !== toolId)
    }
  }

  return {
    enabledTools,
    enableAll,
    disableAll,
    toggle
  }
}
