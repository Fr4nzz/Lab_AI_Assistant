<script setup lang="ts">
const { isAdmin, fetchAdminStatus, updatesInfo, isCheckingUpdates, isUpdating, checkForUpdates, triggerUpdate } = useAdmin()
const toast = useToast()

// Check admin status on mount
onMounted(async () => {
  await fetchAdminStatus()

  // If admin, check for updates initially
  if (isAdmin.value) {
    await checkForUpdates()

    // Then poll every 5 minutes
    setInterval(async () => {
      if (isAdmin.value) {
        await checkForUpdates()
      }
    }, 5 * 60 * 1000)
  }
})

const showEmailsModal = ref(false)

async function handleUpdate() {
  if (!updatesInfo.value?.hasUpdates || isUpdating.value) return

  try {
    const result = await triggerUpdate()
    toast.add({
      title: 'Actualizando...',
      description: result.message,
      icon: 'i-lucide-refresh-cw',
      color: 'primary'
    })
  } catch (error: any) {
    toast.add({
      title: 'Error al actualizar',
      description: error.message || 'No se pudo actualizar la aplicación',
      icon: 'i-lucide-alert-circle',
      color: 'error'
    })
  }
}

async function handleRefreshUpdates() {
  await checkForUpdates()
  if (updatesInfo.value?.hasUpdates) {
    toast.add({
      title: 'Actualizaciones disponibles',
      description: `${updatesInfo.value.behindCount} commits nuevos`,
      icon: 'i-lucide-arrow-down-circle',
      color: 'primary'
    })
  } else {
    toast.add({
      title: 'Sin actualizaciones',
      description: 'Estás en la última versión',
      icon: 'i-lucide-check-circle',
      color: 'neutral'
    })
  }
}
</script>

<template>
  <div v-if="isAdmin" class="space-y-1">
    <!-- Manage Allowed Emails -->
    <UButton
      variant="ghost"
      color="neutral"
      block
      class="justify-start"
      @click="showEmailsModal = true"
    >
      <span class="flex items-center gap-2">
        <UIcon name="i-lucide-users" class="w-4 h-4" />
        Usuarios permitidos
      </span>
    </UButton>

    <!-- Update Button -->
    <div class="flex items-center gap-1">
      <UButton
        variant="ghost"
        :color="updatesInfo?.hasUpdates ? 'primary' : 'neutral'"
        class="flex-1 justify-start"
        :disabled="!updatesInfo?.hasUpdates || isUpdating"
        :loading="isUpdating"
        @click="handleUpdate"
      >
        <span class="flex items-center gap-2">
          <UIcon
            :name="isUpdating ? 'i-lucide-loader-2' : 'i-lucide-download'"
            class="w-4 h-4"
            :class="{ 'animate-spin': isUpdating }"
          />
          <span>Actualizar</span>
          <UBadge
            v-if="updatesInfo?.hasUpdates && updatesInfo.behindCount > 0"
            size="xs"
            color="primary"
            variant="subtle"
          >
            {{ updatesInfo.behindCount }}
          </UBadge>
        </span>
      </UButton>

      <UTooltip text="Buscar actualizaciones">
        <UButton
          variant="ghost"
          color="neutral"
          size="xs"
          icon="i-lucide-refresh-cw"
          :loading="isCheckingUpdates"
          @click="handleRefreshUpdates"
        />
      </UTooltip>
    </div>

    <!-- Current version info -->
    <div v-if="updatesInfo" class="px-2 py-1 text-xs text-muted">
      <span class="font-mono">{{ updatesInfo.currentBranch }}@{{ updatesInfo.localCommit }}</span>
    </div>

    <!-- Allowed Emails Modal -->
    <SidebarAllowedEmailsModal v-model:open="showEmailsModal" />
  </div>
</template>
