// Composable to check if OAuth is configured
export function useAuthConfig() {
  const authConfig = useState<{ oauthEnabled: boolean; provider: string | null } | null>('authConfig', () => null)
  const pending = useState('authConfigPending', () => false)

  async function fetchConfig() {
    if (authConfig.value !== null || pending.value) return authConfig.value

    pending.value = true
    try {
      const data = await $fetch('/api/auth/config')
      authConfig.value = data
    } catch {
      // If we can't fetch config, assume OAuth is not enabled
      authConfig.value = { oauthEnabled: false, provider: null }
    } finally {
      pending.value = false
    }

    return authConfig.value
  }

  return {
    authConfig,
    fetchConfig,
    isOAuthEnabled: computed(() => authConfig.value?.oauthEnabled ?? false)
  }
}
