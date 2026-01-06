/**
 * Forward apply-preprocessing request to backend.
 * Applies AI's rotation + crop choices to images.
 */
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const backendUrl = config.backendUrl || 'http://localhost:8000'

  const body = await readBody(event)

  const response = await fetch(`${backendUrl}/api/apply-preprocessing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    const errorText = await response.text()
    console.error('[API/apply-preprocessing] Backend error:', response.status, errorText)
    throw createError({
      statusCode: response.status,
      message: errorText
    })
  }

  return await response.json()
})
