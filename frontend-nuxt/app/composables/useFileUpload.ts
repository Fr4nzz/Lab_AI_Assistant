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

export function useFileUploadWithStatus(_chatId: string) {
  const files = ref<FileWithStatus[]>([])
  const toast = useToast()

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
          // Fire and forget - don't await
          processImageRotation(fileWithStatus.file).then(rotationResult => {
            const currentIndex = files.value.findIndex(f => f.id === fileWithStatus.id)
            if (currentIndex === -1) return // File was removed

            if (rotationResult.wasRotated && rotationResult.rotatedFile && rotationResult.rotatedDataUrl) {
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

              // Show notification
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

  // Get info about rotated files for display in AI response
  const rotatedFilesInfo = computed(() =>
    files.value
      .filter(f => f.wasRotated && f.rotationInfo)
      .map(f => ({
        fileName: f.originalFile?.name || f.file.name,
        rotation: f.rotationInfo!.rotation,
        model: f.rotationInfo!.model,
        timing: f.rotationInfo!.timing,
        rotatedUrl: f.previewUrl
      }))
  )

  function removeFile(id: string) {
    const file = files.value.find(f => f.id === id)
    if (!file) return

    if (file.previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(file.previewUrl)
    }
    files.value = files.value.filter(f => f.id !== id)
  }

  function clearFiles() {
    if (files.value.length === 0) return
    files.value.forEach(fileWithStatus => {
      if (fileWithStatus.previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(fileWithStatus.previewUrl)
      }
    })
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
    rotatedFilesInfo,
    addFiles: uploadFiles,
    removeFile,
    clearFiles,
    autoRotateEnabled
  }
}
