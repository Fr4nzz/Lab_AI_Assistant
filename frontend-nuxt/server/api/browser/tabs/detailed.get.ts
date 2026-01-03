/**
 * Server-side proxy for browser tabs API.
 * Proxies requests to backend to avoid Local Network Access prompts
 * when frontend is accessed via Cloudflare tunnel.
 */
export default defineEventHandler(async () => {
  const config = useRuntimeConfig()
  const backendUrl = config.backendUrl || 'http://localhost:8000'

  try {
    const response = await fetch(`${backendUrl}/api/browser/tabs/detailed`)

    if (!response.ok) {
      throw createError({
        statusCode: response.status,
        message: `Backend error: ${response.statusText}`
      })
    }

    return await response.json()
  } catch (error) {
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error
    }
    console.error('[API/browser/tabs] Error:', error)
    throw createError({
      statusCode: 503,
      message: 'Backend not available'
    })
  }
})
