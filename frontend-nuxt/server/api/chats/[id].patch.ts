import { z } from 'zod'
import { updateChatTitle } from '../../utils/db'
import { requireSessionOrInternal } from '../../utils/internalAuth'

defineRouteMeta({
  openAPI: {
    description: 'Update chat properties (title, etc.)',
    tags: ['chat']
  }
})

export default defineEventHandler(async (event) => {
  // Verify user is authenticated (OAuth or internal API key)
  await requireSessionOrInternal(event)

  const { id: chatId } = await getValidatedRouterParams(event, z.object({
    id: z.string()
  }).parse)

  const body = await readValidatedBody(event, z.object({
    title: z.string().optional()
  }).parse)

  if (body.title) {
    await updateChatTitle(chatId, body.title)
    console.log(`[API/chat] Title updated to: "${body.title}"`)
  }

  return { success: true, chatId, title: body.title }
})
