// Global refresh function for sidebar chat list
// This allows other components to trigger a sidebar refresh when needed
// e.g., after a chat title is generated

const refreshCallbacks = ref<Set<() => void>>(new Set())

export function useSidebarRefresh() {
  // Register a refresh callback (called by the layout)
  function registerRefresh(callback: () => void) {
    refreshCallbacks.value.add(callback)
    onUnmounted(() => {
      refreshCallbacks.value.delete(callback)
    })
  }

  // Trigger all registered refresh callbacks (called by chat pages)
  function refreshSidebar() {
    refreshCallbacks.value.forEach(cb => cb())
  }

  return {
    registerRefresh,
    refreshSidebar
  }
}
