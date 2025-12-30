import { z } from 'zod'
import { createChat, addMessage } from '../utils/db'
import { requireSessionOrInternal } from '../utils/internalAuth'

export default defineEventHandler(async (event) => {
  // Verify user is authenticated (OAuth or internal API key)
  await requireSessionOrInternal(event)

  const body = await readValidatedBody(event, z.object({
    id: z.string().optional(),
    title: z.string().optional(),
    message: z.object({
      role: z.string(),
      parts: z.array(z.any()).optional(),
      content: z.string().optional()
    }).optional()
  }).parse)

  // Create shared chat (no user association - visible to all users)
  const chat = await createChat({
    id: body.id,
    title: body.title || 'Nuevo Chat'
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
