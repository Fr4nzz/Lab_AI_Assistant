import { addAllowedEmail, isAdminEmail, getAllowedEmails } from '../../utils/adminConfig'

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
