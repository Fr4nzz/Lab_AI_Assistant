import { findOrCreateUser } from '../../utils/db'
import { isAllowedEmail, isAdminEmail } from '../../utils/adminConfig'

export default defineOAuthGoogleEventHandler({
  async onSuccess(event, { user: googleUser }) {
    // Check if email is in allowed list (admins are always allowed)
    const email = googleUser.email?.toLowerCase() || ''
    const isAdmin = isAdminEmail(email)

    if (!isAdmin && !isAllowedEmail(email)) {
      console.error('Email not in allowed list:', googleUser.email)
      throw createError({
        statusCode: 403,
        message: 'Email not authorized'
      })
    }

    // Find or create user
    const user = await findOrCreateUser({
      email: googleUser.email,
      name: googleUser.name,
      avatar: googleUser.picture,
      provider: 'google',
      providerId: googleUser.sub
    })

    // Set user session (convert null to undefined for type compatibility)
    await setUserSession(event, {
      user: {
        id: user.id,
        email: user.email,
        name: user.name ?? undefined,
        avatar: user.avatar ?? undefined,
        provider: user.provider as 'google' | 'github',
        providerId: user.providerId
      }
    })

    return sendRedirect(event, '/')
  },

  onError(event, error) {
    console.error('Google OAuth error:', error)
    return sendRedirect(event, '/login?error=oauth_failed')
  }
})
