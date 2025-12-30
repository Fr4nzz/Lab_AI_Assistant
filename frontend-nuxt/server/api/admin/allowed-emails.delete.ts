import { removeAllowedEmail, getAllowedEmails } from '../../utils/adminConfig'
import { requireAdmin } from '../../utils/adminAuth'

export default defineEventHandler(async (event) => {
  await requireAdmin(event)

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
