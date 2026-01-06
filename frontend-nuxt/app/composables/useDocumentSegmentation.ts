/**
 * Composable for handling document segmentation using SAM3/Gemini.
 * Detects documents in images and crops them for better processing.
 */

interface SegmentationResult {
  fileId: string
  segmented: boolean
  croppedBase64?: string
  boundingBox?: { x1: number; y1: number; x2: number; y2: number }
  originalSize?: { width: number; height: number }
  croppedSize?: { width: number; height: number }
  prompt?: string
  provider?: string
  reason?: string
}

export function useDocumentSegmentation() {
  const pendingSegmentations = ref<Map<string, Promise<SegmentationResult>>>(new Map())
  const segmentationResults = ref<Map<string, SegmentationResult>>(new Map())

  /**
   * Segments a document from an image.
   * Non-blocking - returns immediately and processes in background.
   *
   * @param fileId - Unique identifier for the file
   * @param base64Data - Base64 encoded image data
   * @param mimeType - MIME type of the image
   * @param prompt - Text prompt for segmentation (default: "document")
   */
  async function segmentDocument(
    fileId: string,
    base64Data: string,
    mimeType: string,
    prompt: string = 'document'
  ): Promise<SegmentationResult> {
    // Check if already processing or processed
    if (segmentationResults.value.has(fileId)) {
      return segmentationResults.value.get(fileId)!
    }

    const existingPromise = pendingSegmentations.value.get(fileId)
    if (existingPromise) {
      return existingPromise
    }

    // Create segmentation promise
    const segmentationPromise = (async (): Promise<SegmentationResult> => {
      try {
        console.log('[useDocumentSegmentation] Segmenting:', fileId, 'prompt:', prompt)

        const response = await $fetch<{
          segmented: boolean
          croppedImage?: string
          boundingBox?: { x1: number; y1: number; x2: number; y2: number }
          originalSize?: { width: number; height: number }
          croppedSize?: { width: number; height: number }
          prompt?: string
          provider?: string
          reason?: string
          error?: string
        }>('/api/segment-document', {
          method: 'POST',
          body: {
            imageBase64: base64Data,
            mimeType,
            prompt
          }
        })

        const result: SegmentationResult = {
          fileId,
          segmented: response.segmented,
          croppedBase64: response.croppedImage,
          boundingBox: response.boundingBox,
          originalSize: response.originalSize,
          croppedSize: response.croppedSize,
          prompt: response.prompt,
          provider: response.provider,
          reason: response.reason
        }

        // Store result
        segmentationResults.value.set(fileId, result)
        pendingSegmentations.value.delete(fileId)

        if (result.segmented) {
          console.log('[useDocumentSegmentation] Document segmented:', {
            fileId,
            provider: result.provider,
            originalSize: result.originalSize,
            croppedSize: result.croppedSize
          })
        } else {
          console.log('[useDocumentSegmentation] No segmentation needed:', {
            fileId,
            reason: result.reason
          })
        }

        return result
      } catch (error) {
        console.error('[useDocumentSegmentation] Segmentation error:', error)
        const fallbackResult: SegmentationResult = {
          fileId,
          segmented: false,
          reason: String(error)
        }
        segmentationResults.value.set(fileId, fallbackResult)
        pendingSegmentations.value.delete(fileId)
        return fallbackResult
      }
    })()

    pendingSegmentations.value.set(fileId, segmentationPromise)
    return segmentationPromise
  }

  /**
   * Gets the segmentation result for a file if available.
   */
  function getSegmentation(fileId: string): SegmentationResult | undefined {
    return segmentationResults.value.get(fileId)
  }

  /**
   * Checks if there are pending segmentations.
   */
  const hasPendingSegmentations = computed(() => pendingSegmentations.value.size > 0)

  /**
   * Waits for all pending segmentations to complete.
   */
  async function waitForPendingSegmentations(): Promise<void> {
    const pending = Array.from(pendingSegmentations.value.values())
    if (pending.length > 0) {
      console.log('[useDocumentSegmentation] Waiting for', pending.length, 'pending segmentations...')
      await Promise.all(pending)
      console.log('[useDocumentSegmentation] All segmentations complete')
    }
  }

  /**
   * Clears segmentation data for a file.
   */
  function clearSegmentation(fileId: string) {
    segmentationResults.value.delete(fileId)
    pendingSegmentations.value.delete(fileId)
  }

  /**
   * Clears all segmentation data.
   */
  function clearAllSegmentations() {
    segmentationResults.value.clear()
    pendingSegmentations.value.clear()
  }

  return {
    segmentDocument,
    getSegmentation,
    hasPendingSegmentations,
    waitForPendingSegmentations,
    clearSegmentation,
    clearAllSegmentations,
    segmentationResults: readonly(segmentationResults)
  }
}
