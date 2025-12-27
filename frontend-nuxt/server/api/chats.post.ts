import { z } from 'zod'
import { createChat, addMessage } from '../utils/db'

export default defineEventHandler(async (event) => {
  const session = await getUserSession(event)

  const body = await readValidatedBody(event, z.object({
    id: z.string().optional(),
    title: z.string().optional(),
    message: z.object({
      role: z.string(),
      parts: z.array(z.any()).optional(),
      content: z.string().optional()
    }).optional()
  }).parse)

  // Get user ID from session
  const userId = session.user?.id || session.id

  // Create chat
  const chat = await createChat({
    id: body.id,
    title: body.title || 'Nuevo Chat',
    userId
  })

  // Add initial message if provided
  if (body.message) {
    const textContent = body.message.content ||
      body.message.parts?.filter((p: any) => p.type === 'text').map((p: any) => p.text).join('') || ''

    await addMessage({
      chatId: chat.id,
      role: body.message.role as 'user' | 'assistant' | 'system',
      content: textContent,
      parts: body.message.parts
    })
  }

  return chat
})
