import { rotateImage, dataUrlToBase64 } from '~/utils/imageRotation'

interface RotationResult {
  fileId: string
  rotation: number
  detected: boolean
  rotatedBase64?: string
}

/**
 * Composable for handling image rotation detection.
 * Detects if images need rotation and applies corrections.
 */
export function useImageRotation() {
  const pendingRotations = ref<Map<string, Promise<RotationResult>>>(new Map())
  const rotationResults = ref<Map<string, RotationResult>>(new Map())

  /**
   * Detects rotation for an image and optionally applies it.
   * Non-blocking - returns immediately and processes in background.
   */
  async function detectRotation(
    fileId: string,
    base64Data: string,
    mimeType: string,
    previewUrl: string
  ): Promise<RotationResult> {
    // Check if already processing or processed
    if (rotationResults.value.has(fileId)) {
      return rotationResults.value.get(fileId)!
    }

    const existingPromise = pendingRotations.value.get(fileId)
    if (existingPromise) {
      return existingPromise
    }

    // Create detection promise
    const rotationPromise = (async (): Promise<RotationResult> => {
      try {
        console.log('[useImageRotation] Detecting rotation for:', fileId)

        const response = await $fetch<{ rotation: number; detected: boolean }>('/api/detect-rotation', {
          method: 'POST',
          body: {
            imageBase64: base64Data,
            mimeType
          }
        })

        let result: RotationResult = {
          fileId,
          rotation: response.rotation,
          detected: response.detected
        }

        // If rotation needed, apply it
        if (response.rotation !== 0) {
          console.log('[useImageRotation] Applying rotation:', response.rotation)
          const rotatedDataUrl = await rotateImage(previewUrl, response.rotation)
          result.rotatedBase64 = dataUrlToBase64(rotatedDataUrl)
        }

        // Store result
        rotationResults.value.set(fileId, result)
        pendingRotations.value.delete(fileId)

        return result
      } catch (error) {
        console.error('[useImageRotation] Detection error:', error)
        const fallbackResult: RotationResult = {
          fileId,
          rotation: 0,
          detected: false
        }
        rotationResults.value.set(fileId, fallbackResult)
        pendingRotations.value.delete(fileId)
        return fallbackResult
      }
    })()

    pendingRotations.value.set(fileId, rotationPromise)
    return rotationPromise
  }

  /**
   * Gets the rotation result for a file if available.
   */
  function getRotation(fileId: string): RotationResult | undefined {
    return rotationResults.value.get(fileId)
  }

  /**
   * Checks if there are pending rotation detections.
   */
  const hasPendingRotations = computed(() => pendingRotations.value.size > 0)

  /**
   * Clears rotation data for a file.
   */
  function clearRotation(fileId: string) {
    rotationResults.value.delete(fileId)
    pendingRotations.value.delete(fileId)
  }

  /**
   * Clears all rotation data.
   */
  function clearAllRotations() {
    rotationResults.value.clear()
    pendingRotations.value.clear()
  }

  return {
    detectRotation,
    getRotation,
    hasPendingRotations,
    clearRotation,
    clearAllRotations,
    rotationResults: readonly(rotationResults)
  }
}
