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

    const filesWithStatus: FileWithStatus[] = validFiles.map(file => ({
      file,
      id: generateUUID(),
      previewUrl: createObjectUrl(file),
      status: (file.type.startsWith('image/') && autoRotateEnabled.value ? 'processing' : 'uploading') as const,
      rotation: 0,
      wasRotated: false
    }))

    files.value = [...files.value, ...filesWithStatus]

    // Process files
    const uploadPromises = filesWithStatus.map(async (fileWithStatus) => {
      const index = files.value.findIndex(f => f.id === fileWithStatus.id)
      if (index === -1) return

      try {
        let fileToProcess = fileWithStatus.file
        let rotation = 0
        let wasRotated = false
        let newPreviewUrl = fileWithStatus.previewUrl

        // Process image rotation if enabled and it's an image
        if (autoRotateEnabled.value && fileWithStatus.file.type.startsWith('image/')) {
          try {
            const rotationResult = await processImageRotation(fileWithStatus.file)

            if (rotationResult.wasRotated && rotationResult.rotatedFile && rotationResult.rotatedDataUrl) {
              fileToProcess = rotationResult.rotatedFile
              rotation = rotationResult.rotation
              wasRotated = true

              // Revoke old preview URL and use rotated data URL
              URL.revokeObjectURL(fileWithStatus.previewUrl)
              newPreviewUrl = rotationResult.rotatedDataUrl

              // Show notification
              toast.add({
                description: `Imagen rotada ${rotation}° para mejor lectura`,
                icon: 'i-lucide-rotate-cw',
                color: 'info',
                duration: 2000
              })
            }
          } catch (rotationError) {
            console.warn('Rotation detection failed, using original:', rotationError)
          }

          // Update status to uploading after rotation processing
          files.value[index] = {
            ...files.value[index]!,
            status: 'uploading',
            previewUrl: newPreviewUrl,
            file: fileToProcess,
            originalFile: wasRotated ? fileWithStatus.file : undefined,
            rotation,
            wasRotated
          }
        }

        // Convert file to base64
        const base64Data = await fileToBase64(fileToProcess)

        files.value[index] = {
          ...files.value[index]!,
          status: 'uploaded',
          base64Data,
          previewUrl: newPreviewUrl,
          file: fileToProcess,
          rotation,
          wasRotated
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
    files.value.some(f => f.status === 'uploading' || f.status === 'processing')
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

  function removeFile(id: string) {
    const file = files.value.find(f => f.id === id)
    if (!file) return

    // Only revoke if it's a blob URL (not a data URL)
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
    addFiles: uploadFiles,
    removeFile,
    clearFiles,
    autoRotateEnabled
  }
}
