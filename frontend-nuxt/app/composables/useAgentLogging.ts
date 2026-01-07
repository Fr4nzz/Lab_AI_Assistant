/**
 * Composable for managing agent logging toggle.
 * When enabled, the full AI conversation is saved to a file for evaluation/grading.
 * Syncs with database via settings API so it works for both web and Telegram.
 */
export function useAgentLogging() {
  const enableAgentLogging = useState('enableAgentLogging', () => false)
  const isLoaded = useState('agentLoggingLoaded', () => false)

  // Load from API on client side
  async function loadSetting() {
    if (isLoaded.value) return

    try {
      const settings = await $fetch<{ enableAgentLogging?: boolean }>('/api/settings')
      enableAgentLogging.value = settings.enableAgentLogging ?? false
      isLoaded.value = true
    } catch (error) {
      console.error('Failed to load agent logging setting:', error)
    }
  }

  // Save to API when changed
  async function setSetting(value: boolean) {
    enableAgentLogging.value = value
    try {
      await $fetch('/api/settings', {
        method: 'POST',
        body: { enableAgentLogging: value }
      })
    } catch (error) {
      console.error('Failed to save agent logging setting:', error)
    }
  }

  // Load on client
  if (import.meta.client) {
    loadSetting()
  }

  // Watch for external changes and save
  watch(enableAgentLogging, async (newValue, oldValue) => {
    // Only save if the value changed and we've loaded (to avoid saving default on init)
    if (isLoaded.value && newValue !== oldValue) {
      await setSetting(newValue)
    }
  })

  return {
    enableAgentLogging,
    loadSetting,
    setSetting
  }
}
