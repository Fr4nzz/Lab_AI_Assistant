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

// Rotation result stored per file
export interface RotationResult {
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
  const rotationResults = ref<Map<string, RotationResult>>(new Map())

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
          // Store pending state immediately
          rotationResults.value.set(fileWithStatus.id, {
            fileId: fileWithStatus.id,
            fileName: fileWithStatus.file.name,
            rotation: 0,
            wasRotated: false,
            model: null,
            timing: {},
            rotatedUrl: fileWithStatus.previewUrl,
            state: 'pending'
          })

          // Fire and forget - don't await
          processImageRotation(fileWithStatus.file).then(rotationResult => {
            const currentIndex = files.value.findIndex(f => f.id === fileWithStatus.id)

            // Always store the result (even if file was removed, we keep the cache)
            const result: RotationResult = {
              fileId: fileWithStatus.id,
              fileName: fileWithStatus.file.name,
              rotation: rotationResult.rotation,
              wasRotated: rotationResult.wasRotated,
              model: rotationResult.model || null,
              timing: rotationResult.timing || {},
              rotatedUrl: rotationResult.rotatedDataUrl || fileWithStatus.previewUrl,
              state: 'completed'
            }
            rotationResults.value.set(fileWithStatus.id, result)

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
            // Mark as error but keep in cache
            const existing = rotationResults.value.get(fileWithStatus.id)
            if (existing) {
              rotationResults.value.set(fileWithStatus.id, {
                ...existing,
                state: 'error'
              })
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

  // Get rotation results for current files (for display)
  const currentRotationResults = computed(() => {
    const results: RotationResult[] = []
    for (const file of files.value) {
      const result = rotationResults.value.get(file.id)
      if (result) {
        results.push(result)
      }
    }
    return results
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
    addFiles: uploadFiles,
    removeFile,
    clearFiles,
    clearRotationResults,
    autoRotateEnabled
  }
}
