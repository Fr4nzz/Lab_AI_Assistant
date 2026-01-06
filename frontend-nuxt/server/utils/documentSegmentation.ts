/**
 * Server-side document segmentation utilities.
 *
 * Uses SAM3 or Gemini vision via backend endpoint for document detection.
 * Crops images to focus on documents for better AI processing.
 */

import type { ImagePart } from './imageRotation'

export interface SegmentationResult {
  name: string
  segmented: boolean
  boundingBox?: { x1: number; y1: number; x2: number; y2: number }
  originalSize?: { width: number; height: number }
  croppedSize?: { width: number; height: number }
  prompt?: string
  provider?: string
  reason?: string
  error?: string
}

export interface SegmentedImage extends ImagePart {
  segmented?: boolean
  originalData?: string
  segmentationPrompt?: string
}

/**
 * Detects and segments a document from an image using SAM3/Gemini.
 * Calls the backend endpoint which handles model selection.
 * Returns the cropped image data if segmentation was successful.
 */
export async function segmentDocument(
  base64Data: string,
  mimeType: string,
  prompt: string = 'document'
): Promise<{
  segmented: boolean
  croppedImage?: string
  boundingBox?: { x1: number; y1: number; x2: number; y2: number }
  originalSize?: { width: number; height: number }
  croppedSize?: { width: number; height: number }
  provider?: string
  reason?: string
  timing?: number
}> {
  const config = useRuntimeConfig()
  const startTime = Date.now()

  try {
    console.log('[documentSegmentation] Detecting document via backend')

    const response = await fetch(`${config.backendUrl || 'http://localhost:8000'}/api/segment-document`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image: base64Data,
        mimeType,
        prompt,
        padding: 10
      })
    })

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`)
    }

    const result = await response.json()
    const timing = Date.now() - startTime

    if (result.error) {
      console.error(`[documentSegmentation] Backend error (${timing}ms):`, result.error)
      return { segmented: false, reason: result.error, timing }
    }

    if (result.segmented) {
      console.log(`[documentSegmentation] Document segmented: ${result.croppedSize.width}x${result.croppedSize.height} from ${result.originalSize.width}x${result.originalSize.height} in ${timing}ms`)
    } else {
      console.log(`[documentSegmentation] No segmentation needed: ${result.reason} (${timing}ms)`)
    }

    return {
      segmented: result.segmented,
      croppedImage: result.croppedImage,
      boundingBox: result.boundingBox,
      originalSize: result.originalSize,
      croppedSize: result.croppedSize,
      provider: result.provider,
      reason: result.reason,
      timing
    }
  } catch (error) {
    const timing = Date.now() - startTime
    console.error(`[documentSegmentation] Error (${timing}ms):`, error)
    return { segmented: false, reason: String(error), timing }
  }
}

/**
 * Processes multiple images for document segmentation.
 * Segments documents from images that appear to contain documents.
 *
 * @param images - Array of ImagePart objects to process
 * @param prompt - Text prompt for segmentation (default: "document")
 * @returns Object with segmentation results and processed images
 */
export async function processImagesForSegmentation(
  images: ImagePart[],
  prompt: string = 'document'
): Promise<{ results: SegmentationResult[]; processedImages: SegmentedImage[] }> {
  const results: SegmentationResult[] = []
  const processedImages: SegmentedImage[] = []

  for (const image of images) {
    const imageName = image.name || 'image'

    console.log(`[documentSegmentation] Processing ${imageName}`)

    // Skip if no data available
    if (!image.data) {
      console.log(`[documentSegmentation] No data for ${imageName}, skipping`)
      results.push({
        name: imageName,
        segmented: false,
        reason: 'No image data'
      })
      processedImages.push(image)
      continue
    }

    try {
      const segmentResult = await segmentDocument(image.data, image.mediaType, prompt)

      if (segmentResult.segmented && segmentResult.croppedImage) {
        console.log(`[documentSegmentation] Segmented ${imageName}: ${segmentResult.croppedSize?.width}x${segmentResult.croppedSize?.height}`)
        results.push({
          name: imageName,
          segmented: true,
          boundingBox: segmentResult.boundingBox,
          originalSize: segmentResult.originalSize,
          croppedSize: segmentResult.croppedSize,
          prompt,
          provider: segmentResult.provider
        })
        // Replace image data with cropped version
        processedImages.push({
          ...image,
          data: segmentResult.croppedImage,
          url: `data:${image.mediaType};base64,${segmentResult.croppedImage}`,
          originalData: image.data,
          segmented: true,
          segmentationPrompt: prompt
        })
      } else {
        console.log(`[documentSegmentation] No segmentation for ${imageName}: ${segmentResult.reason}`)
        results.push({
          name: imageName,
          segmented: false,
          reason: segmentResult.reason,
          provider: segmentResult.provider
        })
        processedImages.push({
          ...image,
          segmented: false
        })
      }
    } catch (error) {
      console.error(`[documentSegmentation] Error processing ${imageName}:`, error)
      results.push({
        name: imageName,
        segmented: false,
        error: String(error)
      })
      processedImages.push(image)
    }
  }

  return { results, processedImages }
}

/**
 * Replaces image parts in the original parts array with segmented versions.
 */
export function replaceWithSegmentedImages(
  originalParts: unknown[],
  processedImages: SegmentedImage[]
): unknown[] {
  if (!Array.isArray(originalParts)) return originalParts

  const processedByName = new Map<string, SegmentedImage>()
  processedImages.forEach(img => {
    if (img.name) processedByName.set(img.name, img)
  })

  let processedIndex = 0

  return originalParts.map(part => {
    if (typeof part !== 'object' || part === null) return part
    const p = part as Record<string, unknown>

    if (p.type === 'file' && typeof p.mediaType === 'string' && p.mediaType.startsWith('image/')) {
      let processedImage: SegmentedImage | undefined

      // Try to find by name first
      const name = p.name as string | undefined
      if (name && processedByName.has(name)) {
        processedImage = processedByName.get(name)!
      } else if (processedIndex < processedImages.length) {
        // Fall back to index-based matching
        processedImage = processedImages[processedIndex++]
      }

      if (processedImage && processedImage.segmented) {
        return {
          ...processedImage,
          originalUrl: p.url // Preserve original for reference
        }
      }
    }

    return part
  })
}
