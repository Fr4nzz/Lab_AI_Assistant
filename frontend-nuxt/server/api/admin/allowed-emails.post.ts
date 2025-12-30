import { addAllowedEmail, getAllowedEmails } from '../../utils/adminConfig'
import { requireAdmin } from '../../utils/adminAuth'

export default defineEventHandler(async (event) => {
  await requireAdmin(event)

  // Get email from body
  const body = await readBody(event)
  const emailToAdd = body?.email

  if (!emailToAdd || typeof emailToAdd !== 'string') {
    throw createError({
      statusCode: 400,
      message: 'Email is required'
    })
  }

  // Validate email format
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(emailToAdd)) {
    throw createError({
      statusCode: 400,
      message: 'Invalid email format'
    })
  }

  const added = addAllowedEmail(emailToAdd)

  return {
    success: true,
    added,
    message: added ? `Added ${emailToAdd}` : `${emailToAdd} already exists`,
    emails: getAllowedEmails()
  }
})
