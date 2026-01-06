/**
 * Image preprocessing utility for the new YOLOE + rotation pipeline.
 *
 * Calls backend endpoints to:
 * 1. Generate labeled rotation variants + YOLOE document crops
 * 2. Send variants to AI for selection
 * 3. Apply AI's choices to original images
 */

import { getUserSettings, type UserSettings } from './db'
import type { ImagePart } from './imageRotation'

// Backend response types
interface ImageVariant {
  data: string  // base64 JPEG
  mimeType: string
  label: string
  imageIndex: number
  type: string  // "rotation" or "crop"
  rotation?: number
}

interface LabelInfo {
  imageIndex: number
  label: string
  type: string
  rotation?: number
}

interface CropInfo {
  imageIndex: number
  hasCrop: boolean
  boundingBox?: { x1: number; y1: number; x2: number; y2: number }
  confidence?: number
  className?: string
}

interface TimingInfo {
  totalMs: number
  yoloeMs?: number
  labelingMs?: number
}

interface PreprocessResponse {
  variants: ImageVariant[]
  labels: LabelInfo[]
  crops: CropInfo[]
  timing: TimingInfo
}

interface PreprocessingChoice {
  imageIndex: number
  rotation: number
  useCrop: boolean
}

interface SelectResponse {
  choices: PreprocessingChoice[]
  timing: number
}

interface ProcessedImage {
  data: string  // base64 JPEG
  mimeType: string
  imageIndex: number
  rotation: number
  cropped: boolean
}

interface ApplyResponse {
  processedImages: ProcessedImage[]
  timing: number
}

// Result interface for the caller
export interface PreprocessingResult {
  processedImages: ImagePart[]
  choices: PreprocessingChoice[]
  crops: CropInfo[]
  timing: {
    preprocessMs: number
    selectMs: number
    applyMs: number
    totalMs: number
  }
}

/**
 * Process images through the new preprocessing pipeline.
 *
 * @param backendUrl - Backend API URL
 * @param imageParts - Array of image parts to process
 * @param visitorId - User's visitor ID for settings lookup
 * @returns Processed images ready for AI consumption
 */
export async function processImagesWithPreprocessing(
  backendUrl: string,
  imageParts: ImagePart[],
  visitorId?: string
): Promise<PreprocessingResult> {
  const startTime = Date.now()

  // Get user settings for preprocessing model and thinking level
  let settings: UserSettings = {
    chatModel: 'gemini-3-flash-preview',
    mainThinkingLevel: 'low',
    preprocessingModel: 'gemini-flash-lite-latest',
    preprocessingThinkingLevel: 'low'
  }

  if (visitorId) {
    try {
      settings = await getUserSettings(visitorId)
    } catch (e) {
      console.log('[Preprocessing] Could not load user settings, using defaults')
    }
  }

  console.log(`[Preprocessing] Using model: ${settings.preprocessingModel}, thinking: ${settings.preprocessingThinkingLevel}`)

  // Convert image parts to backend format
  const images = imageParts.map(part => ({
    data: part.url || part.data || '',
    mimeType: part.mediaType,
    name: part.name
  }))

  // Step 1: Generate labeled rotation variants + YOLOE crops
  console.log(`[Preprocessing] Step 1: Generating variants for ${images.length} images`)
  const preprocessResponse = await fetch(`${backendUrl}/api/preprocess-images`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      images,
      preprocessingModel: settings.preprocessingModel,
      thinkingLevel: settings.preprocessingThinkingLevel
    })
  })

  if (!preprocessResponse.ok) {
    const error = await preprocessResponse.text()
    throw new Error(`Preprocessing failed: ${error}`)
  }

  const preprocessResult: PreprocessResponse = await preprocessResponse.json()
  const preprocessMs = preprocessResult.timing.totalMs

  console.log(`[Preprocessing] Generated ${preprocessResult.variants.length} variants in ${preprocessMs}ms`)

  // Step 2: Send variants to AI for selection
  console.log(`[Preprocessing] Step 2: AI selecting best options`)
  const selectResponse = await fetch(`${backendUrl}/api/select-preprocessing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      variants: preprocessResult.variants,
      labels: preprocessResult.labels,
      preprocessingModel: settings.preprocessingModel,
      thinkingLevel: settings.preprocessingThinkingLevel
    })
  })

  if (!selectResponse.ok) {
    const error = await selectResponse.text()
    throw new Error(`Selection failed: ${error}`)
  }

  const selectResult: SelectResponse = await selectResponse.json()
  const selectMs = selectResult.timing

  console.log(`[Preprocessing] AI selected options in ${selectMs}ms:`, selectResult.choices)

  // Step 3: Apply AI's choices to original images
  console.log(`[Preprocessing] Step 3: Applying selections`)
  const applyResponse = await fetch(`${backendUrl}/api/apply-preprocessing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      images,
      choices: selectResult.choices,
      crops: preprocessResult.crops
    })
  })

  if (!applyResponse.ok) {
    const error = await applyResponse.text()
    throw new Error(`Apply failed: ${error}`)
  }

  const applyResult: ApplyResponse = await applyResponse.json()
  const applyMs = applyResult.timing

  console.log(`[Preprocessing] Applied selections in ${applyMs}ms`)

  // Convert processed images back to ImagePart format
  const processedImages: ImagePart[] = applyResult.processedImages.map((img, idx) => {
    const originalPart = imageParts[img.imageIndex - 1] || imageParts[idx]
    return {
      type: 'file' as const,
      data: img.data,
      url: `data:${img.mimeType};base64,${img.data}`,
      mediaType: img.mimeType,
      name: originalPart?.name || `image-${img.imageIndex}`
    }
  })

  const totalMs = Date.now() - startTime

  return {
    processedImages,
    choices: selectResult.choices,
    crops: preprocessResult.crops,
    timing: {
      preprocessMs,
      selectMs,
      applyMs,
      totalMs
    }
  }
}

/**
 * Build tool output for displaying in UI.
 */
export function buildPreprocessingToolOutput(
  result: PreprocessingResult,
  originalParts: ImagePart[]
): Record<string, unknown> {
  return {
    processed: originalParts.length,
    rotated: result.choices.filter(c => c.rotation !== 0).length,
    cropped: result.choices.filter(c => c.useCrop).length,
    timing: result.timing,
    results: result.choices.map((choice, idx) => {
      const crop = result.crops.find(c => c.imageIndex === choice.imageIndex)
      const processedImage = result.processedImages[idx]

      return {
        name: originalParts[choice.imageIndex - 1]?.name || `image-${choice.imageIndex}`,
        rotation: choice.rotation,
        useCrop: choice.useCrop,
        hasCrop: crop?.hasCrop || false,
        cropConfidence: crop?.confidence,
        thumbnailUrl: processedImage?.url,
        mediaType: processedImage?.mediaType
      }
    })
  }
}

/**
 * Replace image parts in a message with processed versions.
 */
export function replaceWithProcessedImages(
  parts: any[],
  processedImages: ImagePart[]
): any[] {
  let imageIdx = 0

  return parts.map(part => {
    // Check if this part is an image
    const isImage = part.type === 'file' &&
      (part.mediaType?.startsWith('image/') ||
       part.url?.startsWith('data:image/'))

    if (isImage && imageIdx < processedImages.length) {
      const processed = processedImages[imageIdx]
      imageIdx++

      return {
        type: 'file',
        data: processed.data,
        url: processed.url,
        mediaType: processed.mediaType,
        name: processed.name || part.name
      }
    }

    return part
  })
}
