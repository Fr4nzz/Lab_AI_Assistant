<script setup lang="ts">
const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const { allowedEmails, fetchAllowedEmails, addAllowedEmail, removeAllowedEmail } = useAdmin()
const toast = useToast()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})

const newEmail = ref('')
const isAdding = ref(false)
const isRemoving = ref<string | null>(null)

// Fetch emails when modal opens
watch(isOpen, async (open) => {
  if (open) {
    await fetchAllowedEmails()
  }
})

async function handleAddEmail() {
  if (!newEmail.value.trim()) return

  isAdding.value = true
  try {
    const added = await addAllowedEmail(newEmail.value.trim())
    if (added) {
      toast.add({
        title: 'Email agregado',
        description: `${newEmail.value} ahora puede acceder`,
        icon: 'i-lucide-user-plus',
        color: 'primary'
      })
    } else {
      toast.add({
        title: 'Email ya existe',
        description: `${newEmail.value} ya está en la lista`,
        icon: 'i-lucide-info',
        color: 'neutral'
      })
    }
    newEmail.value = ''
  } catch (error: any) {
    toast.add({
      title: 'Error',
      description: error.message || 'No se pudo agregar el email',
      icon: 'i-lucide-alert-circle',
      color: 'error'
    })
  } finally {
    isAdding.value = false
  }
}

async function handleRemoveEmail(email: string) {
  isRemoving.value = email
  try {
    const removed = await removeAllowedEmail(email)
    if (removed) {
      toast.add({
        title: 'Email eliminado',
        description: `${email} ya no puede acceder`,
        icon: 'i-lucide-user-minus'
      })
    }
  } catch (error: any) {
    toast.add({
      title: 'Error',
      description: error.message || 'No se pudo eliminar el email',
      icon: 'i-lucide-alert-circle',
      color: 'error'
    })
  } finally {
    isRemoving.value = null
  }
}
</script>

<template>
  <UModal v-model:open="isOpen">
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold">Usuarios permitidos</h3>
            <UButton
              icon="i-lucide-x"
              variant="ghost"
              color="neutral"
              size="sm"
              @click="isOpen = false"
            />
          </div>
        </template>

        <div class="space-y-4">
          <!-- Add new email -->
          <form class="flex gap-2" @submit.prevent="handleAddEmail">
            <UInput
              v-model="newEmail"
              type="email"
              placeholder="email@ejemplo.com"
              class="flex-1"
              :disabled="isAdding"
            />
            <UButton
              type="submit"
              icon="i-lucide-plus"
              :loading="isAdding"
              :disabled="!newEmail.trim()"
            >
              Agregar
            </UButton>
          </form>

          <!-- Email list -->
          <div class="border border-default rounded-lg divide-y divide-default max-h-64 overflow-y-auto">
            <div
              v-for="email in allowedEmails"
              :key="email"
              class="flex items-center justify-between px-3 py-2 hover:bg-elevated/50"
            >
              <span class="text-sm truncate">{{ email }}</span>
              <UButton
                icon="i-lucide-trash-2"
                variant="ghost"
                color="error"
                size="xs"
                :loading="isRemoving === email"
                @click="handleRemoveEmail(email)"
              />
            </div>

            <div
              v-if="allowedEmails.length === 0"
              class="px-3 py-4 text-center text-muted text-sm"
            >
              No hay usuarios configurados.
              <br>
              <span class="text-xs">Todos los usuarios pueden acceder.</span>
            </div>
          </div>

          <p class="text-xs text-muted">
            Los administradores siempre pueden acceder, independientemente de esta lista.
          </p>
        </div>
      </UCard>
    </template>
  </UModal>
</template>
