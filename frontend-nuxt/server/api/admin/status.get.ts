import { isAdminEmail } from '../../utils/adminConfig'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()

  // Check if OAuth is configured
  const oauthConfigured = !!(config.oauth?.google?.clientId && config.oauth?.google?.clientSecret)

  // If OAuth is not configured (local dev), treat as admin
  if (!oauthConfigured) {
    return {
      isAdmin: true,
      loggedIn: false,
      localDev: true
    }
  }

  // Check if user is logged in
  const session = await getUserSession(event)
  const userEmail = session?.user?.email

  if (!userEmail) {
    return {
      isAdmin: false,
      loggedIn: false
    }
  }

  return {
    isAdmin: isAdminEmail(userEmail),
    loggedIn: true,
    email: userEmail
  }
})
