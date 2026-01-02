<script setup lang="ts">
const {
  isAdmin,
  fetchAdminStatus,
  updatesInfo,
  isCheckingUpdates,
  isUpdating,
  checkForUpdates,
  triggerUpdate,
  examsLastUpdate,
  isUpdatingExams,
  fetchExamsLastUpdate,
  triggerExamsUpdate,
  ordersLastUpdate,
  isUpdatingOrders,
  fetchOrdersLastUpdate,
  triggerOrdersUpdate
} = useAdmin()
const toast = useToast()

// Check admin status on mount
onMounted(async () => {
  await fetchAdminStatus()

  // If admin, check for updates and exams/orders last update initially
  if (isAdmin.value) {
    await checkForUpdates()
    await fetchExamsLastUpdate()
    await fetchOrdersLastUpdate()

    // Then poll every 5 minutes
    setInterval(async () => {
      if (isAdmin.value) {
        await checkForUpdates()
      }
    }, 5 * 60 * 1000)
  }
})

// Format the exams last update timestamp
const formattedExamsLastUpdate = computed(() => {
  if (!examsLastUpdate.value) return null
  try {
    const date = new Date(examsLastUpdate.value)
    return date.toLocaleDateString('es-EC', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return examsLastUpdate.value
  }
})

// Format the orders last update timestamp
const formattedOrdersLastUpdate = computed(() => {
  if (!ordersLastUpdate.value) return null
  try {
    const date = new Date(ordersLastUpdate.value)
    return date.toLocaleDateString('es-EC', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return ordersLastUpdate.value
  }
})

const showEmailsModal = ref(false)

async function handleUpdate() {
  if (!updatesInfo.value?.hasUpdates || isUpdating.value) return

  try {
    const result = await triggerUpdate()
    const lastChange = result.newCommit?.message ? `\nÚltimo cambio: ${result.newCommit.message}` : ''
    toast.add({
      title: 'Actualización completada',
      description: `${result.message}${lastChange}`,
      icon: 'i-lucide-check-circle',
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

async function handleExamsUpdate() {
  if (isUpdatingExams.value) return

  try {
    const result = await triggerExamsUpdate()
    toast.add({
      title: 'Lista de exámenes actualizada',
      description: result?.message || 'Actualización exitosa',
      icon: 'i-lucide-check-circle',
      color: 'primary'
    })
  } catch (error: any) {
    toast.add({
      title: 'Error al actualizar exámenes',
      description: error.message || 'No se pudo actualizar la lista de exámenes',
      icon: 'i-lucide-alert-circle',
      color: 'error'
    })
  }
}

async function handleOrdersUpdate() {
  if (isUpdatingOrders.value) return

  try {
    const result = await triggerOrdersUpdate()
    toast.add({
      title: 'Lista de órdenes actualizada',
      description: result?.message || 'Actualización exitosa',
      icon: 'i-lucide-check-circle',
      color: 'primary'
    })
  } catch (error: any) {
    toast.add({
      title: 'Error al actualizar órdenes',
      description: error.message || 'No se pudo actualizar la lista de órdenes',
      icon: 'i-lucide-alert-circle',
      color: 'error'
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

    <!-- Update Exams List Button -->
    <UButton
      variant="ghost"
      color="neutral"
      block
      class="justify-start"
      :loading="isUpdatingExams"
      :disabled="isUpdatingExams"
      @click="handleExamsUpdate"
    >
      <span class="flex items-center gap-2">
        <UIcon
          :name="isUpdatingExams ? 'i-lucide-loader-2' : 'i-lucide-file-spreadsheet'"
          class="w-4 h-4"
          :class="{ 'animate-spin': isUpdatingExams }"
        />
        <span>Actualizar lista de exámenes</span>
      </span>
    </UButton>

    <!-- Exams last update info -->
    <div v-if="formattedExamsLastUpdate" class="px-2 py-1 text-xs text-muted">
      <span>Exámenes: {{ formattedExamsLastUpdate }}</span>
    </div>

    <!-- Update Orders List Button -->
    <UButton
      variant="ghost"
      color="neutral"
      block
      class="justify-start"
      :loading="isUpdatingOrders"
      :disabled="isUpdatingOrders"
      @click="handleOrdersUpdate"
    >
      <span class="flex items-center gap-2">
        <UIcon
          :name="isUpdatingOrders ? 'i-lucide-loader-2' : 'i-lucide-list-ordered'"
          class="w-4 h-4"
          :class="{ 'animate-spin': isUpdatingOrders }"
        />
        <span>Actualizar lista de órdenes</span>
      </span>
    </UButton>

    <!-- Orders last update info -->
    <div v-if="formattedOrdersLastUpdate" class="px-2 py-1 text-xs text-muted">
      <span>Órdenes: {{ formattedOrdersLastUpdate }}</span>
    </div>

    <!-- Allowed Emails Modal -->
    <SidebarAllowedEmailsModal v-model:open="showEmailsModal" />
  </div>
</template>
