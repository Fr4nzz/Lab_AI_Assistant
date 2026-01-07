<script setup lang="ts">
import { LazyModalConfirm } from '#components'

const route = useRoute()
const toast = useToast()
const overlay = useOverlay()
const { loggedIn, openInPopup } = useUserSession()
const { isOAuthEnabled } = useAuthConfig()
const { enabledTools } = useEnabledTools()
const { showStats } = useShowStats()
const { enableAgentLogging } = useAgentLogging()

const open = ref(false)
const tabEditorOpen = ref(false)

// Collapsible panel states
const showTools = ref(false)
const showTabs = ref(false)

const deleteModal = overlay.create(LazyModalConfirm, {
  props: {
    title: 'Eliminar chat',
    description: '¿Estás seguro que deseas eliminar este chat? Esta acción no se puede deshacer.'
  }
})

const { data: chats, refresh: refreshChats } = useLazyFetch<Chat[]>('/api/chats', {
  key: 'chats',
  default: () => [],
  transform: data => data.map(chat => ({
    id: chat.id,
    label: chat.title || 'Untitled',
    to: `/chat/${chat.id}`,
    icon: 'i-lucide-message-circle',
    createdAt: chat.createdAt
  }))
})

// Prefetch chats when they become available (non-blocking)
watch(chats, (newChats) => {
  if (newChats?.length) {
    const first5 = newChats.slice(0, 5)
    Promise.all(first5.map(chat => $fetch(`/api/chats/${chat.id}`).catch(() => {})))
  }
}, { once: true })

// Auto-refresh chats when window regains focus (catches Telegram-created chats)
onMounted(() => {
  const onFocus = () => refreshChats()
  window.addEventListener('focus', onFocus)
  onUnmounted(() => window.removeEventListener('focus', onFocus))
})

watch(loggedIn, () => {
  refreshChats()

  open.value = false
})

const { groups } = useChats(chats)

const items = computed(() => groups.value?.flatMap((group) => {
  return [{
    label: group.label,
    type: 'label' as const
  }, ...group.items.map(item => ({
    ...item,
    slot: 'chat' as const,
    icon: undefined,
    class: item.label === 'Untitled' ? 'text-muted' : ''
  }))]
}))

async function deleteChat(id: string) {
  const instance = deleteModal.open()
  const result = await instance.result
  if (!result) {
    return
  }

  await $fetch(`/api/chats/${id}`, { method: 'DELETE' })

  toast.add({
    title: 'Chat eliminado',
    description: 'El chat ha sido eliminado',
    icon: 'i-lucide-trash'
  })

  refreshChats()

  if (route.params.id === id) {
    navigateTo('/')
  }
}

defineShortcuts({
  c: () => {
    navigateTo('/')
  }
})
</script>

<template>
  <UDashboardGroup unit="rem">
    <UDashboardSidebar
      id="default"
      v-model:open="open"
      :min-size="12"
      collapsible
      resizable
      class="bg-elevated/50"
    >
      <template #header="{ collapsed }">
        <NuxtLink to="/" class="flex items-end gap-0.5">
          <Logo class="h-8 w-auto shrink-0" />
          <span v-if="!collapsed" class="text-xl font-bold text-highlighted">Lab Assistant</span>
        </NuxtLink>

        <div v-if="!collapsed" class="flex items-center gap-1.5 ms-auto">
          <UDashboardSearchButton collapsed />
          <UDashboardSidebarCollapse />
        </div>
      </template>

      <template #default="{ collapsed }">
        <!-- Main flex container for the sidebar content -->
        <div class="flex flex-col h-full overflow-hidden">
          <!-- TOP: Sticky new chat button -->
          <div class="shrink-0 pb-2">
            <div class="flex flex-col gap-1.5">
              <UButton
                v-bind="collapsed ? { icon: 'i-lucide-plus' } : { label: 'Nuevo chat' }"
                variant="soft"
                block
                to="/"
                @click="open = false"
              />

              <template v-if="collapsed">
                <UDashboardSearchButton collapsed />
                <UDashboardSidebarCollapse />
              </template>
            </div>
          </div>

          <!-- MIDDLE: Scrollable chat list -->
          <div v-if="!collapsed" class="flex-1 overflow-y-auto min-h-0">
            <UNavigationMenu
              :items="items"
              :collapsed="collapsed"
              orientation="vertical"
              :ui="{ link: 'overflow-hidden' }"
            >
              <template #chat-trailing="{ item }">
                <div class="flex -mr-1.25 translate-x-full group-hover:translate-x-0 transition-transform">
                  <UButton
                    icon="i-lucide-x"
                    color="neutral"
                    variant="ghost"
                    size="xs"
                    class="text-muted hover:text-primary hover:bg-accented/50 focus-visible:bg-accented/50 p-0.5"
                    tabindex="-1"
                    @click.stop.prevent="deleteChat((item as any).id)"
                  />
                </div>
              </template>
            </UNavigationMenu>
          </div>

          <!-- BOTTOM: Sticky settings section with its own scroll -->
          <div v-if="!collapsed" class="shrink-0 max-h-[50%] overflow-y-auto border-t border-default mt-2">
            <div class="space-y-1 pt-2">
              <!-- Tools toggle -->
              <UCollapsible v-model:open="showTools">
                <UButton
                  variant="ghost"
                  color="neutral"
                  block
                  class="justify-between"
                  :ui="{ trailingIcon: 'transition-transform' }"
                  :trailing-icon="showTools ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                >
                  <span class="flex items-center gap-2">
                    <UIcon name="i-lucide-wrench" class="w-4 h-4" />
                    Herramientas
                    <UBadge size="xs" color="neutral" variant="subtle">
                      {{ enabledTools.length }}
                    </UBadge>
                  </span>
                </UButton>
                <template #content>
                  <SidebarToolToggles
                    :model-value="enabledTools"
                    @update:model-value="enabledTools = $event"
                  />
                </template>
              </UCollapsible>

              <!-- Browser Tabs toggle -->
              <UCollapsible v-model:open="showTabs">
                <UButton
                  variant="ghost"
                  color="neutral"
                  block
                  class="justify-between"
                  :ui="{ trailingIcon: 'transition-transform' }"
                  :trailing-icon="showTabs ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                >
                  <span class="flex items-center gap-2">
                    <UIcon name="i-lucide-layout-grid" class="w-4 h-4" />
                    Pestañas
                  </span>
                </UButton>
                <template #content>
                  <SidebarBrowserTabsPanel @open-editor="tabEditorOpen = true" />
                </template>
              </UCollapsible>

              <!-- Stats toggle -->
              <UButton
                variant="ghost"
                color="neutral"
                block
                class="justify-between"
                @click="showStats = !showStats"
              >
                <span class="flex items-center gap-2">
                  <UIcon name="i-lucide-bar-chart-2" class="w-4 h-4" />
                  Mostrar estadísticas
                </span>
                <UIcon
                  :name="showStats ? 'i-lucide-toggle-right' : 'i-lucide-toggle-left'"
                  class="w-5 h-5"
                  :class="showStats ? 'text-primary' : 'text-muted'"
                />
              </UButton>

              <!-- Agent Logging toggle -->
              <UButton
                variant="ghost"
                color="neutral"
                block
                class="justify-between"
                @click="enableAgentLogging = !enableAgentLogging"
              >
                <span class="flex items-center gap-2">
                  <UIcon name="i-lucide-file-text" class="w-4 h-4" />
                  Guardar logs
                </span>
                <UIcon
                  :name="enableAgentLogging ? 'i-lucide-toggle-right' : 'i-lucide-toggle-left'"
                  class="w-5 h-5"
                  :class="enableAgentLogging ? 'text-primary' : 'text-muted'"
                />
              </UButton>

              <!-- Admin Panel -->
              <SidebarAdminPanel />
            </div>
          </div>

          <!-- Collapsed state icons -->
          <div v-if="collapsed" class="mt-auto space-y-1">
            <UTooltip text="Herramientas">
              <UButton
                icon="i-lucide-wrench"
                variant="ghost"
                color="neutral"
                block
                @click="showTools = !showTools"
              />
            </UTooltip>
            <UTooltip text="Pestañas del navegador">
              <UButton
                icon="i-lucide-layout-grid"
                variant="ghost"
                color="neutral"
                block
                @click="showTabs = !showTabs"
              />
            </UTooltip>
            <UTooltip :text="showStats ? 'Ocultar estadísticas' : 'Mostrar estadísticas'">
              <UButton
                icon="i-lucide-bar-chart-2"
                variant="ghost"
                :color="showStats ? 'primary' : 'neutral'"
                block
                @click="showStats = !showStats"
              />
            </UTooltip>
            <UTooltip :text="enableAgentLogging ? 'Desactivar logs' : 'Activar logs'">
              <UButton
                icon="i-lucide-file-text"
                variant="ghost"
                :color="enableAgentLogging ? 'primary' : 'neutral'"
                block
                @click="enableAgentLogging = !enableAgentLogging"
              />
            </UTooltip>
          </div>
        </div>
      </template>

      <template #footer="{ collapsed }">
        <UserMenu v-if="loggedIn" :collapsed="collapsed" />
        <UButton
          v-else-if="isOAuthEnabled"
          :label="collapsed ? '' : 'Iniciar sesión'"
          icon="i-simple-icons-google"
          color="neutral"
          variant="ghost"
          class="w-full"
          @click="openInPopup('/auth/google')"
        />
        <!-- No login button shown when OAuth is not configured -->
      </template>
    </UDashboardSidebar>

    <UDashboardSearch
      placeholder="Buscar chats..."
      :groups="[{
        id: 'links',
        items: [{
          label: 'Nuevo chat',
          to: '/',
          icon: 'i-lucide-square-pen'
        }]
      }, ...groups]"
    />

    <slot />

    <!-- Tab Editor Modal -->
    <TabEditorModal v-model:open="tabEditorOpen" />
  </UDashboardGroup>
</template>
