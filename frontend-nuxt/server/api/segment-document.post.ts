/**
 * Proxy endpoint for document segmentation.
 * Forwards requests to the backend SAM3/Gemini-powered document detector.
 */
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const body = await readBody(event)

  // Support both formats
  const imageData = body.imageBase64 || body.image
  const mimeType = body.mimeType || 'image/jpeg'
  const prompt = body.prompt || 'document'
  const padding = body.padding || 10

  if (!imageData) {
    throw createError({
      statusCode: 400,
      message: 'Missing image data'
    })
  }

  try {
    const backendUrl = config.backendUrl || 'http://localhost:8000'
    console.log('[API/segment-document] Forwarding to backend...', { prompt, padding })

    const response = await fetch(`${backendUrl}/api/segment-document`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image: imageData,
        mimeType,
        prompt,
        padding
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('[API/segment-document] Backend error:', response.status, errorText)
      throw createError({
        statusCode: response.status,
        message: `Backend error: ${errorText}`
      })
    }

    const result = await response.json()
    console.log('[API/segment-document] Result:', {
      segmented: result.segmented,
      provider: result.provider,
      timing: result.timing,
      boundingBox: result.boundingBox
    })

    return result
  } catch (error) {
    console.error('[API/segment-document] Error:', error)

    // Return fallback (no segmentation) on error
    return {
      segmented: false,
      error: String(error)
    }
  }
})
