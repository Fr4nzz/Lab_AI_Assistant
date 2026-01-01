/**
 * Server-side image rotation detection and processing utilities.
 *
 * Races OpenRouter and Gemini vision models for rotation detection.
 * Uses whichever responds faster for better latency.
 * Rotation is applied using sharp library on the server.
 */

import { generateText } from 'ai'
import { createOpenRouter } from '@openrouter/ai-sdk-provider'
import { createGoogleGenerativeAI } from '@ai-sdk/google'
import { getBestVisionModel } from './openrouter-vision-models'
import sharp from 'sharp'

/**
 * Applies rotation to an image using sharp.
 * Returns the rotated image as base64.
 */
async function applyRotation(base64Data: string, rotation: number): Promise<string> {
  const buffer = Buffer.from(base64Data, 'base64')
  const rotated = await sharp(buffer)
    .rotate(rotation)
    .toBuffer()
  return rotated.toString('base64')
}

export interface ImagePart {
  type: 'file'
  mediaType: string
  url: string
  data?: string
  name?: string
  rotation?: number
  rotatedBase64?: string
  rotationPending?: boolean
}

export interface RotationResult {
  name: string
  originalRotation: number
  applied: boolean
  error?: string
}

export interface ProcessedImage {
  original: ImagePart
  rotation: number
  rotatedUrl?: string
  rotatedData?: string
}

/**
 * Detects the rotation needed for an image using vision models.
 * Races OpenRouter and Gemini to use whichever responds faster.
 * Returns 0, 90, 180, or 270 degrees.
 */
export async function detectImageRotation(
  base64Data: string,
  mimeType: string
): Promise<{ rotation: number; detected: boolean; provider?: string; timing?: { openrouter?: number; gemini?: number } }> {
  const config = useRuntimeConfig()

  const hasOpenRouter = !!config.openrouterApiKey
  const hasGemini = !!config.geminiApiKey

  if (!hasOpenRouter && !hasGemini) {
    console.log('[imageRotation] No API keys configured')
    return { rotation: 0, detected: false }
  }

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

  const messages = [
    {
      role: 'user' as const,
      content: [
        { type: 'text' as const, text: prompt },
        {
          type: 'image' as const,
          image: `data:${mimeType};base64,${base64Data}`
        }
      ]
    }
  ]

  // Track timing for both providers
  const timing: { openrouter?: number; gemini?: number } = {}
  let winnerProvider = ''

  // Create promises for both providers
  const promises: Promise<{ rotation: number; detected: boolean; provider: string }>[] = []

  // OpenRouter promise
  if (hasOpenRouter) {
    const openRouterPromise = (async () => {
      const startTime = Date.now()
      try {
        const modelId = await getBestVisionModel()
        console.log('[imageRotation] OpenRouter using model:', modelId)

        const openrouter = createOpenRouter({
          apiKey: config.openrouterApiKey
        })

        const { text } = await generateText({
          model: openrouter(modelId),
          messages,
          temperature: 0.1,
          maxTokens: 10
        })

        timing.openrouter = Date.now() - startTime
        const rotation = parseInt(text.trim(), 10)

        if ([0, 90, 180, 270].includes(rotation)) {
          console.log(`[imageRotation] OpenRouter detected: ${rotation}° in ${timing.openrouter}ms`)
          return { rotation, detected: true, provider: 'openrouter' }
        }
        console.log(`[imageRotation] OpenRouter invalid response: ${text} (${timing.openrouter}ms)`)
        return { rotation: 0, detected: false, provider: 'openrouter' }
      } catch (error) {
        timing.openrouter = Date.now() - startTime
        console.error(`[imageRotation] OpenRouter error (${timing.openrouter}ms):`, error)
        throw error
      }
    })()
    promises.push(openRouterPromise)
  }

  // Gemini promise
  if (hasGemini) {
    const geminiPromise = (async () => {
      const startTime = Date.now()
      try {
        const google = createGoogleGenerativeAI({
          apiKey: config.geminiApiKey
        })

        console.log('[imageRotation] Gemini using model: gemini-2.5-flash')

        const { text } = await generateText({
          model: google('gemini-2.5-flash'),
          messages,
          temperature: 0.1,
          maxTokens: 10
        })

        timing.gemini = Date.now() - startTime
        const rotation = parseInt(text.trim(), 10)

        if ([0, 90, 180, 270].includes(rotation)) {
          console.log(`[imageRotation] Gemini detected: ${rotation}° in ${timing.gemini}ms`)
          return { rotation, detected: true, provider: 'gemini' }
        }
        console.log(`[imageRotation] Gemini invalid response: ${text} (${timing.gemini}ms)`)
        return { rotation: 0, detected: false, provider: 'gemini' }
      } catch (error) {
        timing.gemini = Date.now() - startTime
        console.error(`[imageRotation] Gemini error (${timing.gemini}ms):`, error)
        throw error
      }
    })()
    promises.push(geminiPromise)
  }

  try {
    // Race both providers - use first successful response
    const result = await Promise.race(promises)
    winnerProvider = result.provider

    // Log the winner and timing comparison
    console.log(`[imageRotation] 🏆 WINNER: ${winnerProvider.toUpperCase()}`)

    // Wait a bit for the other to complete for timing comparison
    setTimeout(() => {
      console.log(`[imageRotation] ⏱️ TIMING COMPARISON:`)
      console.log(`   OpenRouter: ${timing.openrouter ? timing.openrouter + 'ms' : 'not completed/errored'}`)
      console.log(`   Gemini:     ${timing.gemini ? timing.gemini + 'ms' : 'not completed/errored'}`)
      if (timing.openrouter && timing.gemini) {
        const diff = Math.abs(timing.openrouter - timing.gemini)
        const faster = timing.gemini < timing.openrouter ? 'Gemini' : 'OpenRouter'
        console.log(`   ${faster} was ${diff}ms faster`)
      }
    }, 5000) // Wait 5 seconds for slower provider to complete

    return { ...result, timing }
  } catch (error) {
    // If race fails, try to get any successful result
    const results = await Promise.allSettled(promises)
    for (const result of results) {
      if (result.status === 'fulfilled' && result.value.detected) {
        return { ...result.value, timing }
      }
    }
    console.error('[imageRotation] All providers failed')
    return { rotation: 0, detected: false, timing }
  }
}

/**
 * Processes multiple images for rotation.
 * Uses already-rotated data from frontend when available.
 * Falls back to detection if rotation is pending.
 */
export async function processImagesForRotation(
  images: ImagePart[]
): Promise<{ results: RotationResult[]; processedImages: ImagePart[] }> {
  const results: RotationResult[] = []
  const processedImages: ImagePart[] = []

  for (const image of images) {
    const imageName = image.name || 'image'

    console.log(`[imageRotation] Processing ${imageName}:`, {
      hasRotatedBase64: !!image.rotatedBase64,
      rotation: image.rotation,
      rotationPending: image.rotationPending
    })

    // Case 1: Already has rotated data from frontend (rotation was applied client-side)
    if (image.rotatedBase64) {
      const rotationDegrees = image.rotation || 0
      console.log(`[imageRotation] Using pre-rotated data for ${imageName}: ${rotationDegrees}deg`)
      results.push({
        name: imageName,
        originalRotation: rotationDegrees,
        applied: rotationDegrees !== 0
      })
      // Use the rotated data
      processedImages.push({
        ...image,
        data: image.rotatedBase64,
        url: `data:${image.mediaType};base64,${image.rotatedBase64}`
      })
      continue
    }

    // Case 2: Frontend completed detection and determined no rotation needed
    if (image.rotation === 0 && image.rotationPending === false) {
      console.log(`[imageRotation] No rotation needed for ${imageName} (frontend verified)`)
      results.push({
        name: imageName,
        originalRotation: 0,
        applied: false
      })
      processedImages.push(image)
      continue
    }

    // Case 3: Frontend detection completed but rotation != 0 and no rotatedBase64
    // This shouldn't happen normally, but handle it gracefully
    if (image.rotation !== undefined && image.rotation !== 0 && !image.rotatedBase64) {
      console.log(`[imageRotation] Frontend detected ${image.rotation}deg but no rotated data for ${imageName}`)
      results.push({
        name: imageName,
        originalRotation: image.rotation,
        applied: false,
        error: 'Frontend rotation data missing'
      })
      processedImages.push(image)
      continue
    }

    // Case 4: Need to detect rotation (rotation is pending or unknown)
    if (image.data && (image.rotationPending === true || image.rotation === undefined)) {
      console.log(`[imageRotation] Detecting rotation for ${imageName} (pending: ${image.rotationPending})`)
      try {
        const { rotation, detected } = await detectImageRotation(image.data, image.mediaType)

        if (detected && rotation !== 0) {
          // Apply rotation server-side using sharp
          console.log(`[imageRotation] Server detected ${rotation}deg for ${imageName}, applying rotation...`)
          try {
            const rotatedData = await applyRotation(image.data, rotation)
            console.log(`[imageRotation] Successfully rotated ${imageName} by ${rotation}deg`)
            results.push({
              name: imageName,
              originalRotation: rotation,
              applied: true
            })
            processedImages.push({
              ...image,
              rotation,
              data: rotatedData,
              url: `data:${image.mediaType};base64,${rotatedData}`
            })
          } catch (rotationError) {
            console.error(`[imageRotation] Failed to apply rotation for ${imageName}:`, rotationError)
            results.push({
              name: imageName,
              originalRotation: rotation,
              applied: false,
              error: `Rotation failed: ${String(rotationError)}`
            })
            processedImages.push({
              ...image,
              rotation
            })
          }
        } else {
          console.log(`[imageRotation] No rotation needed for ${imageName} (server verified)`)
          results.push({
            name: imageName,
            originalRotation: 0,
            applied: false
          })
          processedImages.push(image)
        }
      } catch (error) {
        console.error(`[imageRotation] Error processing ${imageName}:`, error)
        results.push({
          name: imageName,
          originalRotation: 0,
          applied: false,
          error: String(error)
        })
        processedImages.push(image)
      }
      continue
    }

    // Case 5: No rotation info and detection not needed - pass through
    console.log(`[imageRotation] Passing through ${imageName} as-is`)
    results.push({
      name: imageName,
      originalRotation: image.rotation || 0,
      applied: false
    })
    processedImages.push(image)
  }

  return { results, processedImages }
}

/**
 * Extracts image parts from message parts array.
 */
export function extractImageParts(parts: unknown[]): ImagePart[] {
  if (!Array.isArray(parts)) return []

  return parts.filter((part): part is ImagePart => {
    if (typeof part !== 'object' || part === null) return false
    const p = part as Record<string, unknown>
    return p.type === 'file' && typeof p.mediaType === 'string' && p.mediaType.startsWith('image/')
  })
}

/**
 * Replaces image parts in the original parts array with processed versions.
 */
export function replaceImageParts(
  originalParts: unknown[],
  processedImages: ImagePart[]
): unknown[] {
  if (!Array.isArray(originalParts)) return originalParts

  const processedByName = new Map<string, ImagePart>()
  processedImages.forEach(img => {
    if (img.name) processedByName.set(img.name, img)
  })

  let processedIndex = 0

  return originalParts.map(part => {
    if (typeof part !== 'object' || part === null) return part
    const p = part as Record<string, unknown>

    if (p.type === 'file' && typeof p.mediaType === 'string' && p.mediaType.startsWith('image/')) {
      // Try to find by name first
      const name = p.name as string | undefined
      if (name && processedByName.has(name)) {
        return processedByName.get(name)!
      }
      // Fall back to index-based matching
      if (processedIndex < processedImages.length) {
        return processedImages[processedIndex++]
      }
    }

    return part
  })
}
