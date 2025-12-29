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
  // Base64 encoded image data URL (data:image/png;base64,...)
  imageDataUrl: z.string().min(1)
})

// Prompt for rotation detection based on GPT-4 Vision best practices
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

  if (!config.openrouterApiKey) {
    console.warn('[API/detect-rotation] No OpenRouter API key configured')
    return {
      rotation: 0,
      model: null,
      success: false,
      error: 'OpenRouter API key not configured'
    }
  }

  const body = await readValidatedBody(event, bodySchema.parse)

  // Extract the base64 data and mime type from the data URL
  const matches = body.imageDataUrl.match(/^data:(.+);base64,(.+)$/)
  if (!matches) {
    return {
      rotation: 0,
      model: null,
      success: false,
      error: 'Invalid image data URL format'
    }
  }

  const mimeType = matches[1]
  const base64Data = matches[2]
  const imageSizeKB = Math.round(base64Data.length * 0.75 / 1024)

  console.log(`[API/detect-rotation] Detecting rotation for image (~${imageSizeKB}KB)...`)

  const openrouter = createOpenRouter({
    apiKey: config.openrouterApiKey
  })

  // Get top 3 free vision models
  const visionModels = await getTopFreeVisionModels(config.openrouterApiKey, 3)
  console.log('[API/detect-rotation] Available vision models:', visionModels)

  const startTime = Date.now()

  // Try each model with fallback
  for (const modelId of visionModels) {
    try {
      console.log(`[API/detect-rotation] Trying model: ${modelId}`)
      const modelStartTime = Date.now()

      // Use extraBody to pass provider.sort for latency optimization
      // https://openrouter.ai/docs/guides/routing/provider-selection
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
              {
                type: 'text',
                text: ROTATION_PROMPT
              },
              {
                type: 'image',
                image: `data:${mimeType};base64,${base64Data}`
              }
            ]
          }
        ],
        temperature: 0.1,
        maxTokens: 10
      })

      const modelMs = Date.now() - modelStartTime

      // Parse the response - should be just a number
      const cleanedText = text.trim().replace(/[^\d]/g, '')
      const rotation = parseInt(cleanedText, 10)

      // Validate the rotation value
      if ([0, 90, 180, 270].includes(rotation)) {
        const totalMs = Date.now() - startTime
        console.log(`[API/detect-rotation] Detected rotation: ${rotation}° (model: ${modelMs}ms, total: ${totalMs}ms)`)
        return {
          rotation,
          model: modelId,
          success: true,
          timing: { modelMs, totalMs }
        }
      } else {
        console.warn(`[API/detect-rotation] Invalid rotation value from model: "${text}"`)
        // Try next model
      }
    } catch (error) {
      console.warn(`[API/detect-rotation] Model ${modelId} failed:`, (error as Error).message)
      // Continue to next model
    }
  }

  // If all models failed, return 0 (no rotation)
  const totalMs = Date.now() - startTime
  console.warn(`[API/detect-rotation] All models failed (${totalMs}ms), defaulting to 0°`)
  return {
    rotation: 0,
    model: null,
    success: false,
    error: 'All vision models failed to detect rotation',
    timing: { totalMs }
  }
})
