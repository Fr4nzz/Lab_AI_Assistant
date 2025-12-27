<script setup lang="ts">
definePageMeta({
  layout: false
})

const { loggedIn } = useUserSession()

// Redirect if already logged in
if (loggedIn.value) {
  navigateTo('/')
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
    <div class="max-w-md w-full space-y-8">
      <div class="text-center">
        <div class="flex justify-center mb-6">
          <Logo class="h-16 w-auto" />
        </div>
        <h1 class="text-3xl font-bold text-gray-900 dark:text-white">
          Lab Assistant
        </h1>
        <p class="mt-2 text-gray-600 dark:text-gray-400">
          Asistente de IA para laboratorio clínico
        </p>
      </div>

      <div class="mt-8 space-y-4">
        <UButton
          to="/auth/google"
          external
          block
          size="lg"
          color="neutral"
          variant="solid"
          icon="i-simple-icons-google"
          class="justify-center"
        >
          Iniciar sesión con Google
        </UButton>

        <p class="text-center text-sm text-gray-500 dark:text-gray-400">
          Solo usuarios autorizados pueden acceder
        </p>
      </div>
    </div>
  </div>
</template>
