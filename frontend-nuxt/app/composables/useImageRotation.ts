import type { RotatedImageResult, RotationDegrees } from '~/utils/imageRotation'
import { processImageRotation, fileToDataUrl, rotateImage } from '~/utils/imageRotation'

export interface ImageRotationState {
  isProcessing: boolean
  processedImages: Map<string, RotatedImageResult>
}

/**
 * Composable for managing image rotation detection and processing
 */
export function useImageRotation() {
  const toast = useToast()
  const isProcessing = ref(false)
  const processedImages = ref<Map<string, RotatedImageResult>>(new Map())

  /**
   * Process a single image for rotation detection
   */
  async function processImage(file: File, fileId: string): Promise<RotatedImageResult> {
    // Skip non-images
    if (!file.type.startsWith('image/')) {
      return {
        originalFile: file,
        rotatedFile: null,
        rotatedDataUrl: null,
        rotation: 0 as RotationDegrees,
        wasRotated: false
      }
    }

    try {
      isProcessing.value = true

      const result = await processImageRotation(file)

      // Store the result
      processedImages.value.set(fileId, result)

      // Show notification if rotated
      if (result.wasRotated) {
        toast.add({
          description: `Imagen rotada ${result.rotation}° para mejor lectura`,
          icon: 'i-lucide-rotate-cw',
          color: 'info',
          duration: 2000
        })
      }

      return result
    } finally {
      isProcessing.value = false
    }
  }

  /**
   * Process multiple images for rotation
   */
  async function processImages(files: Array<{ file: File; id: string }>): Promise<RotatedImageResult[]> {
    const imageFiles = files.filter(f => f.file.type.startsWith('image/'))

    if (imageFiles.length === 0) {
      return []
    }

    isProcessing.value = true

    try {
      const results = await Promise.all(
        imageFiles.map(async ({ file, id }) => {
          const result = await processImageRotation(file)
          processedImages.value.set(id, result)
          return result
        })
      )

      // Count rotated images
      const rotatedCount = results.filter(r => r.wasRotated).length
      if (rotatedCount > 0) {
        toast.add({
          description: `${rotatedCount} imagen(es) rotada(s) automáticamente`,
          icon: 'i-lucide-rotate-cw',
          color: 'info',
          duration: 2000
        })
      }

      return results
    } finally {
      isProcessing.value = false
    }
  }

  /**
   * Get the processed result for a file
   */
  function getProcessedImage(fileId: string): RotatedImageResult | undefined {
    return processedImages.value.get(fileId)
  }

  /**
   * Get the file to use (rotated if available, otherwise original)
   */
  function getFileToUse(fileId: string, originalFile: File): File {
    const result = processedImages.value.get(fileId)
    if (result?.wasRotated && result.rotatedFile) {
      return result.rotatedFile
    }
    return originalFile
  }

  /**
   * Get the preview URL to use (rotated if available)
   */
  function getPreviewUrl(fileId: string, originalPreviewUrl: string): string {
    const result = processedImages.value.get(fileId)
    if (result?.wasRotated && result.rotatedDataUrl) {
      return result.rotatedDataUrl
    }
    return originalPreviewUrl
  }

  /**
   * Clear processed images
   */
  function clearProcessedImages() {
    processedImages.value.clear()
  }

  /**
   * Remove a processed image
   */
  function removeProcessedImage(fileId: string) {
    processedImages.value.delete(fileId)
  }

  return {
    isProcessing: readonly(isProcessing),
    processedImages: readonly(processedImages),
    processImage,
    processImages,
    getProcessedImage,
    getFileToUse,
    getPreviewUrl,
    clearProcessedImages,
    removeProcessedImage
  }
}
