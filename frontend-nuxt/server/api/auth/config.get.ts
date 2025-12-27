// Returns auth configuration (whether OAuth is enabled)
export default defineEventHandler(() => {
  const config = useRuntimeConfig()

  // OAuth is enabled if both client ID and secret are set
  const oauthEnabled = !!(
    config.oauth?.google?.clientId &&
    config.oauth?.google?.clientSecret
  )

  return {
    oauthEnabled,
    provider: oauthEnabled ? 'google' : null
  }
})
