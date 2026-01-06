/**
 * Composable for full image preprocessing pipeline.
 * Runs YOLOE detection + AI-based rotation/crop selection when images are added.
 * Results are cached and used when sending messages.
 */

interface PreprocessingResult {
  fileId: string
  processed: boolean
  processedBase64?: string
  rotation: number
  useCrop: boolean
  timing?: number
  error?: string
}

interface PreprocessingChoice {
  imageIndex: number
  rotation: number
  useCrop: boolean
}

export function useImagePreprocessing() {
  const pendingPreprocessing = ref<Map<string, Promise<PreprocessingResult>>>(new Map())
  const preprocessingResults = ref<Map<string, PreprocessingResult>>(new Map())
  const { settings } = useSettings()

  /**
   * Run full preprocessing pipeline for an image.
   * Non-blocking - returns immediately and processes in background.
   */
  async function preprocessImage(
    fileId: string,
    base64Data: string,
    mimeType: string
  ): Promise<PreprocessingResult> {
    // Check if already processing or processed
    if (preprocessingResults.value.has(fileId)) {
      return preprocessingResults.value.get(fileId)!
    }

    const existingPromise = pendingPreprocessing.value.get(fileId)
    if (existingPromise) {
      return existingPromise
    }

    // Create preprocessing promise
    const preprocessingPromise = (async (): Promise<PreprocessingResult> => {
      const startTime = Date.now()

      try {
        console.log('[useImagePreprocessing] Starting preprocessing for:', fileId)

        // Step 1: Generate variants (rotation + YOLOE crop)
        const preprocessResponse = await $fetch<{
          variants: Array<{ data: string; mimeType: string; label: string; imageIndex: number; type: string }>
          labels: Array<{ imageIndex: number; label: string; type: string }>
          crops: Array<{ imageIndex: number; hasCrop: boolean; boundingBox?: object }>
          timing: { totalMs: number }
        }>('/api/preprocess-images', {
          method: 'POST',
          body: {
            images: [{ data: base64Data, mimeType, name: fileId }]
          }
        })

        console.log('[useImagePreprocessing] Generated variants:', preprocessResponse.variants.length)

        // Step 2: AI selects best rotation + crop
        const selectResponse = await $fetch<{
          choices: PreprocessingChoice[]
          timing: number
        }>('/api/select-preprocessing', {
          method: 'POST',
          body: {
            variants: preprocessResponse.variants,
            labels: preprocessResponse.labels,
            preprocessingModel: settings.value.preprocessingModel,
            thinkingLevel: settings.value.preprocessingThinkingLevel
          }
        })

        const choice = selectResponse.choices[0]
        console.log('[useImagePreprocessing] AI selected:', choice)

        // Step 3: Apply the choice
        const applyResponse = await $fetch<{
          processedImages: Array<{ data: string; rotation: number; cropped: boolean }>
          timing: number
        }>('/api/apply-preprocessing', {
          method: 'POST',
          body: {
            images: [{ data: base64Data, mimeType, name: fileId }],
            choices: selectResponse.choices,
            crops: preprocessResponse.crops
          }
        })

        const processedImage = applyResponse.processedImages[0]
        const totalTime = Date.now() - startTime

        const result: PreprocessingResult = {
          fileId,
          processed: true,
          processedBase64: processedImage?.data,
          rotation: choice?.rotation ?? 0,
          useCrop: choice?.useCrop ?? false,
          timing: totalTime
        }

        console.log('[useImagePreprocessing] Complete:', {
          rotation: result.rotation,
          useCrop: result.useCrop,
          timing: `${totalTime}ms`
        })

        preprocessingResults.value.set(fileId, result)
        pendingPreprocessing.value.delete(fileId)

        return result
      } catch (error) {
        console.error('[useImagePreprocessing] Error:', error)
        const fallbackResult: PreprocessingResult = {
          fileId,
          processed: false,
          rotation: 0,
          useCrop: false,
          error: (error as Error).message
        }
        preprocessingResults.value.set(fileId, fallbackResult)
        pendingPreprocessing.value.delete(fileId)
        return fallbackResult
      }
    })()

    pendingPreprocessing.value.set(fileId, preprocessingPromise)
    return preprocessingPromise
  }

  /**
   * Gets the preprocessing result for a file if available.
   */
  function getPreprocessingResult(fileId: string): PreprocessingResult | undefined {
    return preprocessingResults.value.get(fileId)
  }

  /**
   * Checks if there are pending preprocessing operations.
   */
  const hasPendingPreprocessing = computed(() => pendingPreprocessing.value.size > 0)

  /**
   * Waits for all pending preprocessing to complete.
   */
  async function waitForPendingPreprocessing(): Promise<void> {
    const pending = Array.from(pendingPreprocessing.value.values())
    if (pending.length > 0) {
      console.log('[useImagePreprocessing] Waiting for', pending.length, 'pending...')
      await Promise.all(pending)
      console.log('[useImagePreprocessing] All preprocessing complete')
    }
  }

  /**
   * Clears preprocessing data for a file.
   */
  function clearPreprocessing(fileId: string) {
    preprocessingResults.value.delete(fileId)
    pendingPreprocessing.value.delete(fileId)
  }

  /**
   * Clears all preprocessing data.
   */
  function clearAllPreprocessing() {
    preprocessingResults.value.clear()
    pendingPreprocessing.value.clear()
  }

  return {
    preprocessImage,
    getPreprocessingResult,
    hasPendingPreprocessing,
    waitForPendingPreprocessing,
    clearPreprocessing,
    clearAllPreprocessing,
    preprocessingResults: readonly(preprocessingResults)
  }
}
