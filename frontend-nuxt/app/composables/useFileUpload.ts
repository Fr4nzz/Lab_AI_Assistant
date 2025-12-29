import { FILE_UPLOAD_CONFIG, type FileWithStatus } from '~~/shared/utils/file'
import { generateUUID } from '~/utils/uuid'
import { processImageRotation } from '~/utils/imageRotation'

function createObjectUrl(file: File): string {
  return URL.createObjectURL(file)
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      const base64 = result.split(',')[1]
      resolve(base64 || '')
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// File rotation state (different from RotationResult in imageRotation.ts)
export interface FileRotationState {
  fileId: string
  fileName: string
  rotation: number
  wasRotated: boolean
  model: string | null
  timing: { modelMs?: number; totalMs?: number }
  rotatedUrl: string
  state: 'pending' | 'processing' | 'completed' | 'error'
}

export function useFileUploadWithStatus(_chatId: string) {
  const files = ref<FileWithStatus[]>([])
  const toast = useToast()

  // Track rotation results separately - survives file clearing
  const rotationResults = ref<Map<string, FileRotationState>>(new Map())

  // Setting to enable/disable auto-rotation
  const autoRotateEnabled = ref(true)

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

    // Create file entries with 'uploading' status
    const filesWithStatus: FileWithStatus[] = validFiles.map(file => ({
      file,
      id: generateUUID(),
      previewUrl: createObjectUrl(file),
      status: 'uploading' as const,
      rotation: 0,
      wasRotated: false
    }))

    files.value = [...files.value, ...filesWithStatus]

    // Process files - upload first (fast), then rotate in background
    for (const fileWithStatus of filesWithStatus) {
      const index = files.value.findIndex(f => f.id === fileWithStatus.id)
      if (index === -1) continue

      try {
        // Step 1: Convert to base64 immediately (fast)
        const base64Data = await fileToBase64(fileWithStatus.file)

        // Mark as uploaded immediately - user can send now
        files.value[index] = {
          ...files.value[index]!,
          status: 'uploaded',
          base64Data
        }

        // Step 2: Start rotation detection in background (non-blocking)
        if (autoRotateEnabled.value && fileWithStatus.file.type.startsWith('image/')) {
          // Store pending state immediately (force reactivity by creating new Map)
          const pendingMap = new Map(rotationResults.value)
          pendingMap.set(fileWithStatus.id, {
            fileId: fileWithStatus.id,
            fileName: fileWithStatus.file.name,
            rotation: 0,
            wasRotated: false,
            model: null,
            timing: {},
            rotatedUrl: fileWithStatus.previewUrl,
            state: 'pending'
          })
          rotationResults.value = pendingMap

          // Fire and forget - don't await
          processImageRotation(fileWithStatus.file).then(rotationResult => {
            const currentIndex = files.value.findIndex(f => f.id === fileWithStatus.id)

            // Always store the result (even if file was removed, we keep the cache)
            const result: FileRotationState = {
              fileId: fileWithStatus.id,
              fileName: fileWithStatus.file.name,
              rotation: rotationResult.rotation,
              wasRotated: rotationResult.wasRotated,
              model: rotationResult.model || null,
              timing: rotationResult.timing || {},
              rotatedUrl: rotationResult.rotatedDataUrl || fileWithStatus.previewUrl,
              state: 'completed'
            }
            // Force reactivity by creating new Map
            const newMap = new Map(rotationResults.value)
            newMap.set(fileWithStatus.id, result)
            rotationResults.value = newMap

            // Only update file if it still exists
            if (currentIndex !== -1 && rotationResult.wasRotated && rotationResult.rotatedFile && rotationResult.rotatedDataUrl) {
              // Update with rotated image
              const rotatedBase64 = rotationResult.rotatedDataUrl.split(',')[1] || ''

              // Revoke old preview URL
              const oldPreviewUrl = files.value[currentIndex]!.previewUrl
              if (oldPreviewUrl.startsWith('blob:')) {
                URL.revokeObjectURL(oldPreviewUrl)
              }

              files.value[currentIndex] = {
                ...files.value[currentIndex]!,
                file: rotationResult.rotatedFile,
                previewUrl: rotationResult.rotatedDataUrl,
                base64Data: rotatedBase64,
                rotation: rotationResult.rotation,
                wasRotated: true,
                originalFile: fileWithStatus.file,
                rotationInfo: {
                  rotation: rotationResult.rotation,
                  model: rotationResult.model || null,
                  timing: rotationResult.timing || {}
                }
              }

              // Show notification only if actually rotated
              toast.add({
                description: `Imagen rotada ${rotationResult.rotation}° automáticamente`,
                icon: 'i-lucide-rotate-cw',
                color: 'info',
                duration: 2000
              })

              console.log(`[Upload] Image rotated ${rotationResult.rotation}° in background`)
            }
          }).catch(err => {
            console.warn('[Upload] Background rotation failed:', err)
            // Mark as error but keep in cache (force reactivity by creating new Map)
            const existing = rotationResults.value.get(fileWithStatus.id)
            if (existing) {
              const errorMap = new Map(rotationResults.value)
              errorMap.set(fileWithStatus.id, {
                ...existing,
                state: 'error'
              })
              rotationResults.value = errorMap
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
    }
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
  const uploadedFiles = computed(() =>
    files.value
      .filter(f => f.status === 'uploaded' && f.base64Data)
      .map(f => ({
        type: 'file' as const,
        mediaType: f.file.type,
        url: `data:${f.file.type};base64,${f.base64Data}`,
        data: f.base64Data!,
        name: f.file.name
      }))
  )

  // Get rotation results for current files (for display during editing)
  const currentRotationResults = computed(() => {
    const results: FileRotationState[] = []
    for (const file of files.value) {
      const result = rotationResults.value.get(file.id)
      if (result) {
        results.push(result)
      }
    }
    return results
  })

  // Get rotation results by file IDs (for retrieving results after files are cleared)
  function getRotationResultsByIds(fileIds: string[]): FileRotationState[] {
    const results: FileRotationState[] = []
    for (const id of fileIds) {
      const result = rotationResults.value.get(id)
      if (result) {
        results.push(result)
      }
    }
    return results
  }

  // Check if any rotations are still pending for given file IDs
  function hasCompletedRotations(fileIds: string[]): boolean {
    return fileIds.some(id => {
      const result = rotationResults.value.get(id)
      return result && result.state === 'completed'
    })
  }

  // Check if there are any images with pending rotations
  const hasPendingRotations = computed(() => {
    return files.value.some(f => {
      if (!f.file.type.startsWith('image/')) return false
      const result = rotationResults.value.get(f.id)
      return result && (result.state === 'pending' || result.state === 'processing')
    })
  })

  // Wait for all pending rotations to complete
  // Returns a promise that resolves when all rotations are done
  function waitForRotations(timeoutMs = 60000): Promise<FileRotationState[]> {
    return new Promise((resolve, reject) => {
      const imageFileIds = files.value
        .filter(f => f.file.type.startsWith('image/'))
        .map(f => f.id)

      if (imageFileIds.length === 0) {
        resolve([])
        return
      }

      const startTime = Date.now()

      // Check immediately
      const checkComplete = () => {
        const results: FileRotationState[] = []
        let allDone = true

        for (const id of imageFileIds) {
          const result = rotationResults.value.get(id)
          if (result) {
            if (result.state === 'pending' || result.state === 'processing') {
              allDone = false
            } else {
              results.push(result)
            }
          } else {
            // No result yet, still pending
            allDone = false
          }
        }

        if (allDone) {
          return results
        }

        // Check timeout
        if (Date.now() - startTime > timeoutMs) {
          // Return whatever we have
          return imageFileIds
            .map(id => rotationResults.value.get(id))
            .filter((r): r is FileRotationState => r !== undefined)
        }

        return null // Not done yet
      }

      // Initial check
      const initial = checkComplete()
      if (initial !== null) {
        resolve(initial)
        return
      }

      // Poll for completion
      const interval = setInterval(() => {
        const result = checkComplete()
        if (result !== null) {
          clearInterval(interval)
          resolve(result)
        }
      }, 200) // Check every 200ms

      // Timeout cleanup
      setTimeout(() => {
        clearInterval(interval)
        const finalResults = imageFileIds
          .map(id => rotationResults.value.get(id))
          .filter((r): r is FileRotationState => r !== undefined && r.state === 'completed')
        resolve(finalResults)
      }, timeoutMs)
    })
  }

  // Watch for rotation completions (reactive)
  const rotationResultsReactive = computed(() => {
    // Return a new object when rotationResults changes to trigger reactivity
    return new Map(rotationResults.value)
  })

  // Get info about ALL processed images (for saving with message)
  // This includes both rotated and non-rotated images
  const rotatedFilesInfo = computed(() =>
    currentRotationResults.value
      .filter(r => r.state === 'completed')
      .map(r => ({
        fileName: r.fileName,
        rotation: r.rotation,
        model: r.model,
        timing: r.timing,
        rotatedUrl: r.rotatedUrl,
        state: r.state
      }))
  )

  function removeFile(id: string) {
    const file = files.value.find(f => f.id === id)
    if (!file) return

    if (file.previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(file.previewUrl)
    }
    files.value = files.value.filter(f => f.id !== id)
    // Also remove from rotation cache
    rotationResults.value.delete(id)
  }

  function clearFiles() {
    if (files.value.length === 0) return
    files.value.forEach(fileWithStatus => {
      if (fileWithStatus.previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(fileWithStatus.previewUrl)
      }
    })
    files.value = []
    // Don't clear rotation results - they're needed for display after send
  }

  // Clear rotation results (call after message is sent and displayed)
  function clearRotationResults() {
    rotationResults.value.clear()
  }

  onUnmounted(() => {
    clearFiles()
    clearRotationResults()
  })

  return {
    dropzoneRef,
    isDragging,
    files,
    isUploading,
    uploadedFiles,
    rotatedFilesInfo,
    currentRotationResults,
    rotationResultsReactive,
    getRotationResultsByIds,
    hasCompletedRotations,
    hasPendingRotations,
    waitForRotations,
    addFiles: uploadFiles,
    removeFile,
    clearFiles,
    clearRotationResults,
    autoRotateEnabled
  }
}
