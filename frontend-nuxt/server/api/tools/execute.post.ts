/**
 * Server-side proxy for tools execute API.
 * Proxies requests to backend to avoid Local Network Access prompts
 * when frontend is accessed via Cloudflare tunnel.
 */
import { z } from 'zod'

const bodySchema = z.object({
  tool: z.string(),
  args: z.record(z.unknown())
})

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const backendUrl = config.backendUrl || 'http://localhost:8000'

  const body = await readValidatedBody(event, bodySchema.parse)

  try {
    const response = await fetch(`${backendUrl}/api/tools/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })

    const result = await response.json()

    if (!response.ok) {
      throw createError({
        statusCode: response.status,
        message: result.error || 'Tool execution failed'
      })
    }

    return result
  } catch (error) {
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error
    }
    console.error('[API/tools/execute] Error:', error)
    throw createError({
      statusCode: 503,
      message: 'Backend not available'
    })
  }
})
