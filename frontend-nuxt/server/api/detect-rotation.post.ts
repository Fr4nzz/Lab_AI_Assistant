import { z } from 'zod'

defineRouteMeta({
  openAPI: {
    description: 'Proxy rotation detection to Python backend',
    tags: ['image']
  }
})

const bodySchema = z.object({
  imageDataUrl: z.string().min(1)
})

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const body = await readValidatedBody(event, bodySchema.parse)

  const backendUrl = config.backendUrl || 'http://localhost:8000'

  console.log(`[API/detect-rotation] Proxying to backend: ${backendUrl}/api/detect-rotation`)

  try {
    const response = await fetch(`${backendUrl}/api/detect-rotation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imageDataUrl: body.imageDataUrl })
    })

    if (!response.ok) {
      console.error('[API/detect-rotation] Backend error:', response.status)
      return {
        rotation: 0,
        model: null,
        success: false,
        error: `Backend returned ${response.status}`
      }
    }

    const result = await response.json()
    console.log(`[API/detect-rotation] Backend result: ${result.rotation}° (${result.timing?.totalMs || 0}ms)`)
    return result
  } catch (error) {
    console.error('[API/detect-rotation] Backend connection error:', error)
    return {
      rotation: 0,
      model: null,
      success: false,
      error: 'Backend not available'
    }
  }
})
