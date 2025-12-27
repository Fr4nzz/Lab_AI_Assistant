import { getChats } from '../utils/db'

export default defineEventHandler(async (event) => {
  const session = await getUserSession(event)

  // Get user ID from session (authenticated user or anonymous session)
  const userId = session.user?.id || session.id

  return await getChats(userId)
})
