/**
 * Forward preprocess-images request to backend.
 * Generates rotation variants + YOLOE crop detection.
 */
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const backendUrl = config.backendUrl || 'http://localhost:8000'

  const body = await readBody(event)

  const response = await fetch(`${backendUrl}/api/preprocess-images`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    const errorText = await response.text()
    console.error('[API/preprocess-images] Backend error:', response.status, errorText)
    throw createError({
      statusCode: response.status,
      message: errorText
    })
  }

  return await response.json()
})
