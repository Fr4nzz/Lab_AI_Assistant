/**
 * Server-side image rotation detection and processing utilities.
 *
 * Uses Gemini via backend endpoint for rotation detection.
 * Rotation is applied using sharp library on the server.
 */

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
 * Detects the rotation needed for an image using Gemini vision.
 * Calls the backend endpoint which handles API key rotation.
 * Returns 0, 90, 180, or 270 degrees.
 */
export async function detectImageRotation(
  base64Data: string,
  mimeType: string
): Promise<{ rotation: number; detected: boolean; provider?: string; timing?: number }> {
  const config = useRuntimeConfig()
  const startTime = Date.now()

  try {
    console.log('[imageRotation] Detecting rotation via backend (Gemini)')

    const response = await fetch(`${config.backendUrl || 'http://localhost:8000'}/api/detect-rotation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image: base64Data,
        mimeType
      })
    })

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`)
    }

    const result = await response.json()
    const timing = Date.now() - startTime

    if (result.error) {
      console.error(`[imageRotation] Gemini error (${timing}ms):`, result.error)
      return { rotation: 0, detected: false, provider: 'gemini', timing }
    }

    const rotation = result.rotation
    if ([0, 90, 180, 270].includes(rotation)) {
      console.log(`[imageRotation] Gemini detected: ${rotation}° in ${timing}ms`)
      return { rotation, detected: rotation !== 0, provider: 'gemini', timing }
    }

    console.log(`[imageRotation] Gemini invalid response: ${result.raw} (${timing}ms)`)
    return { rotation: 0, detected: false, provider: 'gemini', timing }
  } catch (error) {
    const timing = Date.now() - startTime
    console.error(`[imageRotation] Error (${timing}ms):`, error)
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
