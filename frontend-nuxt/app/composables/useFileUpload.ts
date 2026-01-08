import { FILE_UPLOAD_CONFIG, type FileWithStatus } from '~~/shared/utils/file'
import { generateUUID } from '~/utils/uuid'
import { segmentImage, segmentedImageToParts } from '~/utils/imageSegmentation'

function createObjectUrl(file: File): string {
  return URL.createObjectURL(file)
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // Remove the data URL prefix to get just the base64 data
      const base64 = result.split(',')[1]
      resolve(base64 || '')
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

export function useFileUploadWithStatus(_chatId: string) {
  const files = ref<FileWithStatus[]>([])
  const toast = useToast()
  const { settings, isLoaded: settingsLoaded, loadSettings } = useSettings()
  // Use new preprocessing pipeline instead of old rotation detection
  const {
    preprocessImage,
    clearPreprocessing,
    clearAllPreprocessing,
    waitForPendingPreprocessing,
    hasPendingPreprocessing
  } = useImagePreprocessing()

  // Cache for segmented images (computed async)
  const segmentedCache = ref<Map<string, Awaited<ReturnType<typeof segmentImage>>>>(new Map())

  async function uploadFiles(newFiles: File[]) {
    // Validate file sizes
    const validFiles = newFiles.filter((file) => {
      if (file.size > FILE_UPLOAD_CONFIG.maxSize) {
        toast.add({
          title: 'Archivo muy grande',
          description: `${file.name} excede el límite de 8MB`,
          icon: 'i-lucide-alert-circle',
          color: 'error'
        })
        return false
      }
      return true
    })

    const filesWithStatus: FileWithStatus[] = validFiles.map(file => ({
      file,
      id: generateUUID(),
      previewUrl: createObjectUrl(file),
      status: 'uploading' as const
    }))

    files.value = [...files.value, ...filesWithStatus]

    // Convert files to base64 (this is the "upload" part)
    const uploadPromises = filesWithStatus.map(async (fileWithStatus) => {
      const index = files.value.findIndex(f => f.id === fileWithStatus.id)
      if (index === -1) return

      try {
        const base64Data = await fileToBase64(fileWithStatus.file)

        // Mark as uploaded immediately - user can continue interacting
        files.value[index] = {
          ...files.value[index]!,
          status: 'uploaded',
          base64Data
        }

        // Start full preprocessing pipeline in background for images (non-blocking)
        if (fileWithStatus.file.type.startsWith('image/')) {
          preprocessImage(
            fileWithStatus.id,
            base64Data,
            fileWithStatus.file.type
          ).then(async (result) => {
            // Update file with preprocessing result when complete
            const currentIndex = files.value.findIndex(f => f.id === fileWithStatus.id)
            if (currentIndex !== -1) {
              files.value[currentIndex] = {
                ...files.value[currentIndex]!,
                rotation: result.rotation,
                // Store the fully processed image (rotated + cropped)
                rotatedBase64: result.processedBase64,
                // Store additional preprocessing info
                preprocessed: result.processed,
                useCrop: result.useCrop
              }
              console.log('[useFileUpload] Preprocessing complete:', {
                fileId: fileWithStatus.id,
                rotation: result.rotation,
                useCrop: result.useCrop,
                timing: result.timing
              })

              // Pre-compute segmentation in background (uses processed image)
              const finalBase64 = result.processedBase64 || base64Data
              try {
                // Ensure settings are loaded before checking segmentImages
                if (!settingsLoaded.value) {
                  console.log('[useFileUpload] Waiting for settings to load...')
                  await loadSettings()
                }

                const segmented = await segmentImage(finalBase64, fileWithStatus.file.type)
                segmentedCache.value.set(fileWithStatus.id, segmented)

                // Detailed logging
                const segmentSizes = segmented.segments.map(s => Math.round(s.length * 0.75 / 1024))
                console.log('[useFileUpload] Segmentation complete:', {
                  fileId: fileWithStatus.id,
                  fileName: fileWithStatus.file.name,
                  segments: segmented.segments.length,
                  labels: segmented.labels,
                  segmentSizesKB: segmentSizes,
                  segmentImagesEnabled: settings.value.segmentImages,
                  settingsLoaded: settingsLoaded.value
                })

                // Save debug images to backend if segmentation is enabled
                if (settings.value.segmentImages) {
                  console.log('[useFileUpload] Saving segment debug images to backend...')
                  try {
                    const debugResult = await $fetch('/api/save-segment-debug', {
                      method: 'POST',
                      body: {
                        fileId: fileWithStatus.id,
                        fileName: fileWithStatus.file.name,
                        fullImage: finalBase64,
                        segments: segmented.segments,
                        labels: segmented.labels
                      }
                    })
                    console.log('[useFileUpload] Debug images saved:', debugResult)
                  } catch (debugError) {
                    console.warn('[useFileUpload] Failed to save segment debug images:', debugError)
                  }
                } else {
                  console.log('[useFileUpload] Segmentation disabled, not saving debug images')
                }
              } catch (segError) {
                console.error('[useFileUpload] Segmentation error:', segError)
              }
            }
          }).catch((error) => {
            console.error('[useFileUpload] Preprocessing error:', error)
            // Mark as processed (no changes) even on error
            const currentIndex = files.value.findIndex(f => f.id === fileWithStatus.id)
            if (currentIndex !== -1) {
              files.value[currentIndex] = {
                ...files.value[currentIndex]!,
                rotation: 0,
                preprocessed: false
              }
            }
          })
        }
      } catch (error) {
        const errorMessage = (error as Error).message || 'Error al procesar archivo'
        toast.add({
          title: 'Error',
          description: errorMessage,
          icon: 'i-lucide-alert-circle',
          color: 'error'
        })
        files.value[index] = {
          ...files.value[index]!,
          status: 'error',
          error: errorMessage
        }
      }
    })

    await Promise.allSettled(uploadPromises)
  }

  const { dropzoneRef, isDragging } = useFileUpload({
    accept: FILE_UPLOAD_CONFIG.acceptPattern,
    multiple: true,
    onUpdate: uploadFiles
  })

  const isUploading = computed(() =>
    files.value.some(f => f.status === 'uploading')
  )

  // Format files for AI SDK message parts
  // Uses preprocessed (rotated + cropped) images if available
  // When segmentImages is enabled, includes 9 additional segment images for each image
  const uploadedFiles = computed(() => {
    const result: Array<{
      type: 'file'
      mediaType: string
      url: string
      data: string
      name: string
      rotation?: number
      rotatedBase64?: string
      preprocessed?: boolean
      useCrop?: boolean
      preprocessingPending?: boolean
      segmentLabel?: string
    }> = []

    for (const f of files.value) {
      if (f.status !== 'uploaded' || !f.base64Data) continue

      const isImage = f.file.type.startsWith('image/')
      // Use preprocessed data if available (already rotated + cropped), otherwise original
      const base64 = f.rotatedBase64 || f.base64Data!

      // Check if segmentation is enabled and we have cached segments
      const segmented = segmentedCache.value.get(f.id)
      if (settings.value.segmentImages && isImage && segmented) {
        // Add full image first
        result.push({
          type: 'file' as const,
          mediaType: f.file.type,
          url: `data:${f.file.type};base64,${base64}`,
          data: base64,
          name: f.file.name,
          rotation: f.rotation,
          rotatedBase64: f.rotatedBase64,
          preprocessed: f.preprocessed,
          useCrop: f.useCrop,
          preprocessingPending: false
        })

        // Add 9 segments with labels
        for (let i = 0; i < segmented.segments.length; i++) {
          const segmentData = segmented.segments[i]
          const label = segmented.labels[i]
          result.push({
            type: 'file' as const,
            mediaType: f.file.type,
            url: `data:${f.file.type};base64,${segmentData}`,
            data: segmentData,
            name: `${f.file.name} [${label}]`,
            segmentLabel: label
          })
        }
      } else {
        // No segmentation - just add the file normally
        result.push({
          type: 'file' as const,
          mediaType: f.file.type,
          url: `data:${f.file.type};base64,${base64}`,
          data: base64,
          name: f.file.name,
          rotation: f.rotation,
          rotatedBase64: f.rotatedBase64,
          preprocessed: f.preprocessed,
          useCrop: f.useCrop,
          preprocessingPending: isImage && f.rotation === undefined
        })
      }
    }

    return result
  })

  function removeFile(id: string) {
    const file = files.value.find(f => f.id === id)
    if (!file) return

    URL.revokeObjectURL(file.previewUrl)
    clearPreprocessing(id)
    segmentedCache.value.delete(id)
    files.value = files.value.filter(f => f.id !== id)
  }

  function clearFiles() {
    if (files.value.length === 0) return
    files.value.forEach(fileWithStatus => URL.revokeObjectURL(fileWithStatus.previewUrl))
    clearAllPreprocessing()
    segmentedCache.value.clear()
    files.value = []
  }

  onUnmounted(() => {
    clearFiles()
  })

  return {
    dropzoneRef,
    isDragging,
    files,
    isUploading,
    uploadedFiles,
    addFiles: uploadFiles,
    removeFile,
    clearFiles,
    waitForPendingPreprocessing,
    hasPendingPreprocessing
  }
}
