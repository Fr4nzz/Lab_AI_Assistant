import { requireAdmin } from '../../utils/adminAuth'

export default defineEventHandler(async (event) => {
  await requireAdmin(event)

  const config = useRuntimeConfig()
  const backendUrl = config.public.backendUrl || 'http://localhost:8000'

  try {
    const response = await $fetch<{
      prompts: Record<string, string>
      sections: Array<{ key: string; label: string; description: string }>
    }>(`${backendUrl}/api/prompts`)

    return response
  } catch (error: any) {
    throw createError({
      statusCode: error.statusCode || 500,
      message: error.message || 'Failed to fetch prompts'
    })
  }
})
