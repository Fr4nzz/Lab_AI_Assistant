import { requireAdmin } from '../../utils/adminAuth'

export default defineEventHandler(async (event) => {
  await requireAdmin(event)

  const body = await readBody(event)

  if (!body?.prompts) {
    throw createError({
      statusCode: 400,
      message: 'Missing prompts in request body'
    })
  }

  const config = useRuntimeConfig()
  const backendUrl = config.public.backendUrl || 'http://localhost:8000'

  try {
    const response = await $fetch<{ success: boolean; message: string }>(`${backendUrl}/api/prompts`, {
      method: 'POST',
      body: { prompts: body.prompts }
    })

    return response
  } catch (error: any) {
    throw createError({
      statusCode: error.statusCode || 500,
      message: error.message || 'Failed to update prompts'
    })
  }
})
