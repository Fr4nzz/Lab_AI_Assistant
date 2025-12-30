import { H3Event } from 'h3'
import { isAdminEmail } from './adminConfig'

/**
 * Check if the current request has admin access.
 * Returns true if:
 * - OAuth is not configured (local dev mode)
 * - User is logged in and their email is in ADMIN_EMAILS
 *
 * Throws 401 if not authenticated (when OAuth is configured)
 * Throws 403 if not an admin (when OAuth is configured)
 */
export async function requireAdmin(event: H3Event): Promise<{ isLocalDev: boolean; email?: string }> {
  const config = useRuntimeConfig()

  // Check if OAuth is configured
  const oauthConfigured = !!(config.oauth?.google?.clientId && config.oauth?.google?.clientSecret)

  // If OAuth is not configured (local dev), allow access
  if (!oauthConfigured) {
    return { isLocalDev: true }
  }

  // OAuth is configured, require authentication
  const session = await getUserSession(event)
  const userEmail = session?.user?.email

  if (!userEmail) {
    throw createError({
      statusCode: 401,
      message: 'Not authenticated'
    })
  }

  if (!isAdminEmail(userEmail)) {
    throw createError({
      statusCode: 403,
      message: 'Admin access required'
    })
  }

  return { isLocalDev: false, email: userEmail }
}
