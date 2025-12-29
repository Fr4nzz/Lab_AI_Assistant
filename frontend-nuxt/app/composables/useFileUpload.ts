import { FILE_UPLOAD_CONFIG, type FileWithStatus } from '~~/shared/utils/file'
import { generateUUID } from '~/utils/uuid'

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
  const { detectRotation, clearRotation, clearAllRotations } = useImageRotation()

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

        // Start rotation detection in background for images (non-blocking)
        if (fileWithStatus.file.type.startsWith('image/')) {
          detectRotation(
            fileWithStatus.id,
            base64Data,
            fileWithStatus.file.type,
            fileWithStatus.previewUrl
          ).then((result) => {
            // Update file with rotation info when detection completes
            const currentIndex = files.value.findIndex(f => f.id === fileWithStatus.id)
            if (currentIndex !== -1 && result.rotation !== 0) {
              files.value[currentIndex] = {
                ...files.value[currentIndex]!,
                rotation: result.rotation,
                rotatedBase64: result.rotatedBase64
              }
              console.log('[useFileUpload] Rotation detected:', result.rotation, 'for file:', fileWithStatus.id)
            }
          }).catch((error) => {
            console.error('[useFileUpload] Rotation detection error:', error)
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
  // Uses rotated base64 if rotation was detected and applied
  const uploadedFiles = computed(() =>
    files.value
      .filter(f => f.status === 'uploaded' && f.base64Data)
      .map(f => {
        // Use rotated data if available, otherwise original
        const base64 = f.rotatedBase64 || f.base64Data!
        return {
          type: 'file' as const,
          mediaType: f.file.type,
          url: `data:${f.file.type};base64,${base64}`,
          data: base64,
          name: f.file.name,
          rotation: f.rotation || 0
        }
      })
  )

  function removeFile(id: string) {
    const file = files.value.find(f => f.id === id)
    if (!file) return

    URL.revokeObjectURL(file.previewUrl)
    clearRotation(id)
    files.value = files.value.filter(f => f.id !== id)
  }

  function clearFiles() {
    if (files.value.length === 0) return
    files.value.forEach(fileWithStatus => URL.revokeObjectURL(fileWithStatus.previewUrl))
    clearAllRotations()
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
    clearFiles
  }
}
