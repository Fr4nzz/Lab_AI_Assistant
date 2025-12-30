/**
 * Server-side image rotation detection and processing utilities.
 *
 * Uses the existing /api/detect-rotation endpoint for rotation detection.
 * Rotation is applied using canvas on the client side (the rotated data
 * comes from the frontend when available).
 */

import { generateText } from 'ai'
import { createOpenRouter } from '@openrouter/ai-sdk-provider'
import { getBestVisionModel } from './openrouter-vision-models'

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
 * Detects the rotation needed for an image using the vision model.
 * Returns 0, 90, 180, or 270 degrees.
 */
export async function detectImageRotation(
  base64Data: string,
  mimeType: string
): Promise<{ rotation: number; detected: boolean }> {
  const config = useRuntimeConfig()

  if (!config.openrouterApiKey) {
    console.log('[imageRotation] No OpenRouter key configured')
    return { rotation: 0, detected: false }
  }

  try {
    const modelId = await getBestVisionModel()
    console.log('[imageRotation] Using model:', modelId)

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
              image: `data:${mimeType};base64,${base64Data}`
            }
          ]
        }
      ],
      temperature: 0.1,
      maxTokens: 10
    })

    const rotation = parseInt(text.trim(), 10)

    if ([0, 90, 180, 270].includes(rotation)) {
      console.log('[imageRotation] Detected rotation:', rotation)
      return { rotation, detected: true }
    }

    console.log('[imageRotation] Invalid response:', text)
    return { rotation: 0, detected: false }
  } catch (error) {
    console.error('[imageRotation] Detection error:', error)
    return { rotation: 0, detected: false }
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

    // Case 1: Already has rotated data from frontend
    if (image.rotatedBase64 && image.rotation && image.rotation !== 0) {
      console.log(`[imageRotation] Using pre-rotated data for ${imageName}: ${image.rotation}deg`)
      results.push({
        name: imageName,
        originalRotation: image.rotation,
        applied: true
      })
      processedImages.push({
        ...image,
        data: image.rotatedBase64,
        url: `data:${image.mediaType};base64,${image.rotatedBase64}`
      })
      continue
    }

    // Case 2: Rotation is known but was 0 (no rotation needed)
    if (image.rotation === 0) {
      console.log(`[imageRotation] No rotation needed for ${imageName}`)
      results.push({
        name: imageName,
        originalRotation: 0,
        applied: false
      })
      processedImages.push(image)
      continue
    }

    // Case 3: Need to detect rotation (rotation is pending or unknown)
    if (image.data && image.rotationPending !== false) {
      console.log(`[imageRotation] Detecting rotation for ${imageName}`)
      try {
        const { rotation, detected } = await detectImageRotation(image.data, image.mediaType)

        if (detected && rotation !== 0) {
          // We detected rotation is needed, but we can't apply it server-side without sharp
          // The image will still be sent as-is, but we report the rotation
          // The AI will see the rotated image and can describe it accordingly
          results.push({
            name: imageName,
            originalRotation: rotation,
            applied: false,
            error: 'Server-side rotation not available'
          })
          processedImages.push({
            ...image,
            rotation
          })
        } else {
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

    // Case 4: No rotation info and no pending detection - pass through
    results.push({
      name: imageName,
      originalRotation: 0,
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
