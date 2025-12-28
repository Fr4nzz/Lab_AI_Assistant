/**
 * Composable for managing LLM stats display preference
 * Persists to localStorage
 */
export function useShowStats() {
  const showStats = useState<boolean>('show-stats', () => {
    if (import.meta.client) {
      const stored = localStorage.getItem('lab-assistant-show-stats')
      return stored !== null ? stored === 'true' : true // Default to true
    }
    return true
  })

  // Watch for changes and persist
  watch(showStats, (value) => {
    if (import.meta.client) {
      localStorage.setItem('lab-assistant-show-stats', String(value))
    }
  })

  return {
    showStats
  }
}
