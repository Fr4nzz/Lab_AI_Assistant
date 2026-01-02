/**
 * Proxy endpoint for image rotation detection.
 * Forwards requests to the backend Gemini-powered rotation detector.
 */
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const body = await readBody(event)

  // Support both formats: frontend uses imageBase64, backend uses image
  const imageData = body.imageBase64 || body.image
  const mimeType = body.mimeType || 'image/jpeg'

  if (!imageData) {
    throw createError({
      statusCode: 400,
      message: 'Missing image data'
    })
  }

  try {
    const backendUrl = config.backendUrl || 'http://localhost:8000'
    console.log('[API/detect-rotation] Forwarding to backend...')

    const response = await fetch(`${backendUrl}/api/detect-rotation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image: imageData,
        mimeType
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('[API/detect-rotation] Backend error:', response.status, errorText)
      throw createError({
        statusCode: response.status,
        message: `Backend error: ${errorText}`
      })
    }

    const result = await response.json()
    console.log('[API/detect-rotation] Result:', {
      rotation: result.rotation,
      detected: result.detected,
      timing: result.timing
    })

    return result
  } catch (error) {
    console.error('[API/detect-rotation] Error:', error)

    // Return fallback (no rotation) on error
    return {
      rotation: 0,
      detected: false,
      error: String(error)
    }
  }
})
