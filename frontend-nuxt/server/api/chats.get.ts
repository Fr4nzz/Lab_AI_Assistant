import { getChats } from '../utils/db'
import { requireSessionOrInternal } from '../utils/internalAuth'

export default defineEventHandler(async (event) => {
  // Verify user is authenticated (OAuth or internal API key)
  await requireSessionOrInternal(event)

  // Return ALL chats (shared across all users)
  return await getChats()
})
