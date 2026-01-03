import { requireAdmin } from '../../../utils/adminAuth'

export default defineEventHandler(async (event) => {
  await requireAdmin(event)

  const config = useRuntimeConfig()
  const backendUrl = config.backendUrl || 'http://localhost:8000'

  try {
    const response = await $fetch<{
      prompts: Record<string, string>
    }>(`${backendUrl}/api/prompts/defaults`)

    return response
  } catch (error: any) {
    throw createError({
      statusCode: error.statusCode || 500,
      message: error.message || 'Failed to fetch default prompts'
    })
  }
})
