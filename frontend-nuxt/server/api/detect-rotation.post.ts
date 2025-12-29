import { z } from 'zod'
import { generateText } from 'ai'
import { createOpenRouter } from '@openrouter/ai-sdk-provider'
import { getBestVisionModel } from '../utils/openrouter-vision-models'

defineRouteMeta({
  openAPI: {
    description: 'Detect if an image needs rotation correction.',
    tags: ['image']
  }
})

const bodySchema = z.object({
  imageBase64: z.string(),
  mimeType: z.string()
})

/**
 * Detects if an image needs rotation correction.
 * Uses a vision model to analyze the image orientation.
 * Returns the rotation degrees needed (0, 90, 180, 270).
 */
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()

  if (!config.openrouterApiKey) {
    console.log('[detect-rotation] No OpenRouter key configured')
    return { rotation: 0, detected: false }
  }

  const body = await readValidatedBody(event, bodySchema.parse)

  try {
    const modelId = await getBestVisionModel()
    console.log('[detect-rotation] Using model:', modelId)

    const openrouter = createOpenRouter({
      apiKey: config.openrouterApiKey
    })

    const prompt = `Analyze this image and determine if it needs rotation correction.

Look for these indicators of incorrect orientation:
- Text that is sideways or upside down
- People or objects that appear tilted
- Horizon lines that aren't horizontal
- Buildings or structures that lean unnaturally

Respond with ONLY one of these values:
- 0 (image is correctly oriented)
- 90 (image needs 90 degrees clockwise rotation)
- 180 (image is upside down)
- 270 (image needs 90 degrees counter-clockwise rotation)

Just respond with the number, nothing else.`

    const { text } = await generateText({
      model: openrouter(modelId),
      messages: [
        {
          role: 'user',
          content: [
            { type: 'text', text: prompt },
            {
              type: 'image',
              image: `data:${body.mimeType};base64,${body.imageBase64}`
            }
          ]
        }
      ],
      temperature: 0.1,
      maxTokens: 10
    })

    // Parse the rotation value
    const rotation = parseInt(text.trim(), 10)

    if ([0, 90, 180, 270].includes(rotation)) {
      console.log('[detect-rotation] Detected rotation:', rotation)
      return { rotation, detected: true }
    }

    console.log('[detect-rotation] Invalid response:', text)
    return { rotation: 0, detected: false }
  } catch (error) {
    console.error('[detect-rotation] Error:', error)
    return { rotation: 0, detected: false, error: 'Detection failed' }
  }
})
