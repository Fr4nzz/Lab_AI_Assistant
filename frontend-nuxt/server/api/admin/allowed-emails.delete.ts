import { removeAllowedEmail, isAdminEmail, getAllowedEmails } from '../../utils/adminConfig'

export default defineEventHandler(async (event) => {
  // Check if user is logged in
  const session = await getUserSession(event)
  const userEmail = session?.user?.email

  if (!userEmail) {
    throw createError({
      statusCode: 401,
      message: 'Not authenticated'
    })
  }

  // Check if user is admin
  if (!isAdminEmail(userEmail)) {
    throw createError({
      statusCode: 403,
      message: 'Admin access required'
    })
  }

  // Get email from body
  const body = await readBody(event)
  const emailToRemove = body?.email

  if (!emailToRemove || typeof emailToRemove !== 'string') {
    throw createError({
      statusCode: 400,
      message: 'Email is required'
    })
  }

  const removed = removeAllowedEmail(emailToRemove)

  return {
    success: true,
    removed,
    message: removed ? `Removed ${emailToRemove}` : `${emailToRemove} not found`,
    emails: getAllowedEmails()
  }
})
