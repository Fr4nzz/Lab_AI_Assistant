import { getAllowedEmails, isAdminEmail } from '../../utils/adminConfig'

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

  return {
    emails: getAllowedEmails()
  }
})
