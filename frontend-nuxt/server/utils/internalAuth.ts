import { H3Event } from 'h3'

/**
 * Get session for a request, supporting both OAuth and internal API key.
 *
 * For Telegram bot and other internal services, use the X-Internal-Key header
 * with the INTERNAL_API_KEY value from environment.
 *
 * Returns session data if authenticated, null otherwise.
 * Does NOT throw - check the return value.
 */
export async function getSessionOrInternal(event: H3Event): Promise<{ user?: { email?: string }; isInternal?: boolean } | null> {
  const config = useRuntimeConfig()

  // Check for internal API key first
  const internalKey = getHeader(event, 'x-internal-key')
  const configuredKey = process.env.INTERNAL_API_KEY

  // If internal key is configured and matches, allow access
  if (configuredKey && internalKey === configuredKey) {
    return { isInternal: true }
  }

  // Check if OAuth is configured
  const oauthConfigured = !!(config.oauth?.google?.clientId && config.oauth?.google?.clientSecret)

  // If OAuth is not configured (local dev), allow access
  if (!oauthConfigured) {
    return { isInternal: true }
  }

  // Try OAuth session
  try {
    const session = await getUserSession(event)
    if (session?.user) {
      return session
    }
  } catch {
    // Session check failed
  }

  return null
}

/**
 * Require authentication - either OAuth session or internal API key.
 * Throws 401 if not authenticated.
 */
export async function requireSessionOrInternal(event: H3Event): Promise<{ user?: { email?: string }; isInternal?: boolean }> {
  const session = await getSessionOrInternal(event)

  if (!session) {
    throw createError({
      statusCode: 401,
      message: 'Authentication required. Use OAuth or provide X-Internal-Key header.'
    })
  }

  return session
}
