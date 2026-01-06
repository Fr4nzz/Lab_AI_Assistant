/**
 * Forward select-preprocessing request to backend.
 * AI selects best rotation + crop option.
 */
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const backendUrl = config.backendUrl || 'http://localhost:8000'

  const body = await readBody(event)

  const response = await fetch(`${backendUrl}/api/select-preprocessing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    const errorText = await response.text()
    console.error('[API/select-preprocessing] Backend error:', response.status, errorText)
    throw createError({
      statusCode: response.status,
      message: errorText
    })
  }

  return await response.json()
})
