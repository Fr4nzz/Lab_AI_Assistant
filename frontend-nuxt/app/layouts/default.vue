<script setup lang="ts">
import { LazyModalConfirm } from '#components'

const route = useRoute()
const toast = useToast()
const overlay = useOverlay()
const { loggedIn, openInPopup } = useUserSession()
const { isOAuthEnabled } = useAuthConfig()
const { enabledTools } = useEnabledTools()

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

const { data: chats, refresh: refreshChats } = await useFetch<Chat[]>('/api/chats', {
  key: 'chats',
  transform: data => data.map(chat => ({
    id: chat.id,
    label: chat.title || 'Untitled',
    to: `/chat/${chat.id}`,
    icon: 'i-lucide-message-circle',
    createdAt: chat.createdAt
  }))
})

onNuxtReady(async () => {
  const first10 = (chats.value || []).slice(0, 10)
  for (const chat of first10) {
    // prefetch the chat and let the browser cache it
    await $fetch(`/api/chats/${chat.id}`)
  }
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

        <UNavigationMenu
          v-if="!collapsed"
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

        <!-- Collapsible panels for Tools and Browser Tabs -->
        <div v-if="!collapsed" class="mt-auto space-y-1 border-t border-default pt-2">
          <!-- Tools toggle -->
          <UCollapsible v-model:open="showTools">
            <UButton
              variant="ghost"
              color="neutral"
              block
              class="justify-between"
              :ui="{ trailingIcon: 'transition-transform' }"
              :trailing-icon="showTools ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
              @click="showTools = !showTools"
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
              <SidebarToolToggles v-model="enabledTools" />
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
              @click="showTabs = !showTabs"
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
