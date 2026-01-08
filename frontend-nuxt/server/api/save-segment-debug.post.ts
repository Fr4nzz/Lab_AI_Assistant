/**
 * Forward save-segment-debug request to backend.
 * Saves segmented images to debug folder for inspection.
 */
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const backendUrl = config.backendUrl || 'http://localhost:8000'

  const body = await readBody(event)

  console.log(`[API/save-segment-debug] Saving ${body.segments?.length || 0} segments for: ${body.fileName}`)

  const response = await fetch(`${backendUrl}/api/save-segment-debug`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    const errorText = await response.text()
    console.error('[API/save-segment-debug] Backend error:', response.status, errorText)
    throw createError({
      statusCode: response.status,
      message: errorText
    })
  }

  const result = await response.json()
  console.log(`[API/save-segment-debug] Saved successfully:`, result.files?.length || 0, 'files')
  return result
})
