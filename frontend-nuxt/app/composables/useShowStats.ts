/**
 * Composable for managing stats display toggle in chat messages.
 * Persists the preference to localStorage.
 */
export function useShowStats() {
  const showStats = useState('showStats', () => {
    // Default to true, will be hydrated from localStorage on client
    return true
  })

  // Load from localStorage on client side
  if (import.meta.client) {
    const stored = localStorage.getItem('showStats')
    if (stored !== null) {
      showStats.value = stored === 'true'
    }
  }

  // Watch for changes and persist to localStorage
  watch(showStats, (value) => {
    if (import.meta.client) {
      localStorage.setItem('showStats', String(value))
    }
  })

  return {
    showStats
  }
}
