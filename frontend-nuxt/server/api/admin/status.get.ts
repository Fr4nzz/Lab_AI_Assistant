import { isAdminEmail } from '../../utils/adminConfig'

export default defineEventHandler(async (event) => {
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
