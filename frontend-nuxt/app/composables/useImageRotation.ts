import { rotateImage, dataUrlToBase64 } from '~/utils/imageRotation'

export interface RotationResult {
  fileId: string
  fileName: string
  rotation: number
  detected: boolean
  rotatedBase64?: string
  status: 'pending' | 'processing' | 'completed' | 'error'
  error?: string
}

/**
 * Composable for handling image rotation detection.
 * Detects if images need rotation and applies corrections.
 * Exposes state for UI display of rotation tool.
 */
export function useImageRotation() {
  const rotationStates = ref<Map<string, RotationResult>>(new Map())
  const pendingPromises = ref<Map<string, Promise<RotationResult>>>(new Map())

  /**
   * Detects rotation for an image and optionally applies it.
   * Non-blocking - returns immediately and processes in background.
   */
  async function detectRotation(
    fileId: string,
    fileName: string,
    base64Data: string,
    mimeType: string,
    previewUrl: string
  ): Promise<RotationResult> {
    // Check if already processed
    const existing = rotationStates.value.get(fileId)
    if (existing && existing.status === 'completed') {
      return existing
    }

    // Check if already processing
    const existingPromise = pendingPromises.value.get(fileId)
    if (existingPromise) {
      return existingPromise
    }

    // Initialize state as pending
    const initialState: RotationResult = {
      fileId,
      fileName,
      rotation: 0,
      detected: false,
      status: 'pending'
    }
    rotationStates.value.set(fileId, initialState)

    // Create detection promise
    const rotationPromise = (async (): Promise<RotationResult> => {
      try {
        // Update to processing
        rotationStates.value.set(fileId, {
          ...initialState,
          status: 'processing'
        })

        console.log('[useImageRotation] Detecting rotation for:', fileName)

        const response = await $fetch<{ rotation: number; detected: boolean }>('/api/detect-rotation', {
          method: 'POST',
          body: {
            imageBase64: base64Data,
            mimeType
          }
        })

        let result: RotationResult = {
          fileId,
          fileName,
          rotation: response.rotation,
          detected: response.detected,
          status: 'completed'
        }

        // If rotation needed, apply it
        if (response.rotation !== 0) {
          console.log('[useImageRotation] Applying rotation:', response.rotation)
          const rotatedDataUrl = await rotateImage(previewUrl, response.rotation)
          result.rotatedBase64 = dataUrlToBase64(rotatedDataUrl)
        }

        // Store result
        rotationStates.value.set(fileId, result)
        pendingPromises.value.delete(fileId)

        return result
      } catch (error) {
        console.error('[useImageRotation] Detection error:', error)
        const errorResult: RotationResult = {
          fileId,
          fileName,
          rotation: 0,
          detected: false,
          status: 'error',
          error: (error as Error).message || 'Detection failed'
        }
        rotationStates.value.set(fileId, errorResult)
        pendingPromises.value.delete(fileId)
        return errorResult
      }
    })()

    pendingPromises.value.set(fileId, rotationPromise)
    return rotationPromise
  }

  /**
   * Gets the rotation state for a file.
   */
  function getRotationState(fileId: string): RotationResult | undefined {
    return rotationStates.value.get(fileId)
  }

  /**
   * Gets all rotation states for display.
   */
  const allRotationStates = computed(() => Array.from(rotationStates.value.values()))

  /**
   * Gets only the processing/pending rotation states.
   */
  const pendingRotationStates = computed(() =>
    Array.from(rotationStates.value.values()).filter(
      r => r.status === 'pending' || r.status === 'processing'
    )
  )

  /**
   * Checks if there are pending rotation detections.
   */
  const hasPendingRotations = computed(() =>
    Array.from(rotationStates.value.values()).some(
      r => r.status === 'pending' || r.status === 'processing'
    )
  )

  /**
   * Waits for all pending rotations to complete.
   */
  async function waitForAllRotations(): Promise<void> {
    const promises = Array.from(pendingPromises.value.values())
    if (promises.length > 0) {
      await Promise.allSettled(promises)
    }
  }

  /**
   * Clears rotation data for a file.
   */
  function clearRotation(fileId: string) {
    rotationStates.value.delete(fileId)
    pendingPromises.value.delete(fileId)
  }

  /**
   * Clears all rotation data.
   */
  function clearAllRotations() {
    rotationStates.value.clear()
    pendingPromises.value.clear()
  }

  return {
    detectRotation,
    getRotationState,
    allRotationStates,
    pendingRotationStates,
    hasPendingRotations,
    waitForAllRotations,
    clearRotation,
    clearAllRotations
  }
}
