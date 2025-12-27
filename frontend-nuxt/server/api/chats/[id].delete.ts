import { z } from 'zod'
import { deleteChat, getChat } from '../../utils/db'

export default defineEventHandler(async (event) => {
  const { id: chatId } = await getValidatedRouterParams(event, z.object({
    id: z.string()
  }).parse)

  // Verify chat exists
  const chat = await getChat(chatId)
  if (!chat) {
    throw createError({ statusCode: 404, message: 'Chat not found' })
  }

  await deleteChat(chatId)

  return { success: true }
})
