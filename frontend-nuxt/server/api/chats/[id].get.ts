import { z } from 'zod'
import { getChat } from '../../utils/db'

export default defineEventHandler(async (event) => {
  const { id: chatId } = await getValidatedRouterParams(event, z.object({
    id: z.string()
  }).parse)

  const chat = await getChat(chatId)

  if (!chat) {
    throw createError({ statusCode: 404, message: 'Chat not found' })
  }

  // Convert messages to AI SDK format
  const formattedMessages = chat.messages?.map((msg: {
    id: string
    role: string
    content: string | null
    parts: unknown
    createdAt: Date
  }) => ({
    id: msg.id,
    role: msg.role,
    content: msg.content,
    parts: msg.parts ? (typeof msg.parts === 'string' ? JSON.parse(msg.parts) : msg.parts) : undefined,
    createdAt: msg.createdAt
  })) || []

  return {
    id: chat.id,
    title: chat.title,
    userId: chat.userId,
    createdAt: chat.createdAt,
    messages: formattedMessages
  }
})
