/**
 * Composable for managing agent logging toggle.
 * When enabled, the full AI conversation is saved to a file for evaluation/grading.
 * Syncs with database via settings API so it works for both web and Telegram.
 */
export function useAgentLogging() {
  const enableAgentLogging = useState('enableAgentLogging', () => false)
  const isLoaded = useState('agentLoggingLoaded', () => false)
  const isLoading = useState('agentLoggingLoading', () => false)

  // Load from API on client side
  async function loadSetting() {
    if (isLoaded.value || isLoading.value) return

    isLoading.value = true
    try {
      const settings = await $fetch<{ enableAgentLogging?: boolean }>('/api/settings')
      // Set isLoaded BEFORE updating value to prevent watch from re-saving
      isLoaded.value = true
      enableAgentLogging.value = settings.enableAgentLogging ?? false
    } catch (error) {
      console.error('Failed to load agent logging setting:', error)
      isLoaded.value = true // Mark as loaded even on error to prevent retry loops
    } finally {
      isLoading.value = false
    }
  }

  // Save to API when changed (called directly from toggle click)
  async function setSetting(value: boolean) {
    enableAgentLogging.value = value
    // Only save if we've loaded (to avoid race conditions)
    if (!isLoaded.value) return

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

  return {
    enableAgentLogging,
    loadSetting,
    setSetting
  }
}
