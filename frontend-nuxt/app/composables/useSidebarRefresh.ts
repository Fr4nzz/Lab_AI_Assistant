// Global refresh function for sidebar chat list
// This allows other components to trigger a sidebar refresh when needed
// e.g., after a chat title is generated

const refreshCallbacks = ref<Set<() => void>>(new Set())

export function useSidebarRefresh() {
  // Register a refresh callback (called by the layout)
  function registerRefresh(callback: () => void) {
    refreshCallbacks.value.add(callback)
    console.log('[SidebarRefresh] Registered callback, total:', refreshCallbacks.value.size)
    onUnmounted(() => {
      refreshCallbacks.value.delete(callback)
      console.log('[SidebarRefresh] Unregistered callback, remaining:', refreshCallbacks.value.size)
    })
  }

  // Trigger all registered refresh callbacks (called by chat pages)
  function refreshSidebar() {
    console.log('[SidebarRefresh] Refreshing sidebar, callbacks:', refreshCallbacks.value.size)
    refreshCallbacks.value.forEach(cb => {
      try {
        cb()
        console.log('[SidebarRefresh] Callback executed successfully')
      } catch (e) {
        console.error('[SidebarRefresh] Callback failed:', e)
      }
    })
  }

  return {
    registerRefresh,
    refreshSidebar
  }
}
