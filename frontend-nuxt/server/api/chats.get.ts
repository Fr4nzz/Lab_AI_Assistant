import { getChats } from '../utils/db'

export default defineEventHandler(async (event) => {
  // Verify user is authenticated
  await getUserSession(event)

  // Return ALL chats (shared across all users)
  return await getChats()
})
