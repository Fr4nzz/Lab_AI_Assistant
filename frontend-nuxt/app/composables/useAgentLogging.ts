/**
 * Composable for managing agent logging toggle.
 * When enabled, the full AI conversation is saved to a file for evaluation/grading.
 * Persists the preference to localStorage.
 */
export function useAgentLogging() {
  const enableAgentLogging = useState('enableAgentLogging', () => {
    // Default to false, will be hydrated from localStorage on client
    return false
  })

  // Load from localStorage on client side
  if (import.meta.client) {
    const stored = localStorage.getItem('enableAgentLogging')
    if (stored !== null) {
      enableAgentLogging.value = stored === 'true'
    }
  }

  // Watch for changes and persist to localStorage
  watch(enableAgentLogging, (value) => {
    if (import.meta.client) {
      localStorage.setItem('enableAgentLogging', String(value))
    }
  })

  return {
    enableAgentLogging
  }
}
