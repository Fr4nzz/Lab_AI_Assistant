import { z } from 'zod'
import { getTopFreeVisionModels } from '../utils/openrouter-vision-models'
import { createOpenRouter } from '@openrouter/ai-sdk-provider'
import { generateText } from 'ai'

defineRouteMeta({
  openAPI: {
    description: 'Detect if an image needs rotation to align text properly',
    tags: ['image']
  }
})

const bodySchema = z.object({
  imageDataUrl: z.string().min(1)
})

const ROTATION_PROMPT = `Analyze this image and determine if it needs rotation to make text readable.

TASK: Determine the rotation needed so text reads left-to-right, top-to-bottom.

RULES:
- Return ONLY a single number: 0, 90, 180, or 270
- 0 = Image is correctly oriented (text is readable)
- 90 = Rotate 90° clockwise (text is currently sideways, reading bottom-to-top)
- 180 = Rotate 180° (text is upside down)
- 270 = Rotate 270° clockwise / 90° counter-clockwise (text is sideways, reading top-to-bottom)

GUIDANCE:
- Look at any text, numbers, logos, or writing in the image
- If no text is visible, look at natural orientation cues (faces, objects)
- If the image appears correctly oriented, return 0

IMPORTANT: Respond with ONLY the number (0, 90, 180, or 270). No other text.`

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const startTime = Date.now()

  if (!config.openrouterApiKey) {
    throw createError({
      statusCode: 500,
      message: 'OpenRouter API key not configured'
    })
  }

  const body = await readValidatedBody(event, bodySchema.parse)

  const matches = body.imageDataUrl.match(/^data:(.+);base64,(.+)$/)
  if (!matches) {
    throw createError({
      statusCode: 400,
      message: 'Invalid image data URL format'
    })
  }

  const mimeType = matches[1]
  const base64Data = matches[2]
  const imageSizeKB = Math.round(base64Data.length * 0.75 / 1024)

  console.log(`[API/detect-rotation] Starting (image: ${imageSizeKB}KB)...`)

  const openrouter = createOpenRouter({
    apiKey: config.openrouterApiKey
  })

  // Get top 3 free vision models
  const modelFetchStart = Date.now()
  const visionModels = await getTopFreeVisionModels(config.openrouterApiKey, 3)
  console.log(`[API/detect-rotation] Models fetched in ${Date.now() - modelFetchStart}ms:`, visionModels)

  // Try each model with fallback
  for (const modelId of visionModels) {
    const modelStart = Date.now()
    try {
      console.log(`[API/detect-rotation] Trying: ${modelId}`)

      const model = openrouter(modelId, {
        extraBody: {
          provider: {
            sort: 'latency'
          }
        }
      })

      const { text } = await generateText({
        model,
        messages: [
          {
            role: 'user',
            content: [
              { type: 'text', text: ROTATION_PROMPT },
              { type: 'image', image: `data:${mimeType};base64,${base64Data}` }
            ]
          }
        ],
        temperature: 0.1,
        maxTokens: 10
      })

      const modelTime = Date.now() - modelStart
      const totalTime = Date.now() - startTime

      const cleanedText = text.trim().replace(/[^\d]/g, '')
      const rotation = parseInt(cleanedText, 10)

      if ([0, 90, 180, 270].includes(rotation)) {
        console.log(`[API/detect-rotation] Result: ${rotation}° (model: ${modelTime}ms, total: ${totalTime}ms)`)
        return {
          rotation,
          model: modelId,
          success: true,
          timing: { modelMs: modelTime, totalMs: totalTime }
        }
      } else {
        console.warn(`[API/detect-rotation] Invalid response: "${text}" (${modelTime}ms)`)
      }
    } catch (error) {
      console.warn(`[API/detect-rotation] ${modelId} failed after ${Date.now() - modelStart}ms:`, (error as Error).message)
    }
  }

  const totalTime = Date.now() - startTime
  console.warn(`[API/detect-rotation] All models failed (${totalTime}ms), defaulting to 0°`)
  return {
    rotation: 0,
    model: null,
    success: false,
    error: 'All vision models failed',
    timing: { totalMs: totalTime }
  }
})
