/**
 * Composable for audio recording using MediaRecorder API.
 * Supports recording audio from microphone and returns as a File.
 */
export function useAudioRecorder() {
  const isRecording = ref(false)
  const isPreparing = ref(false)
  const error = ref<string | null>(null)

  let mediaRecorder: MediaRecorder | null = null
  let audioChunks: Blob[] = []
  let stream: MediaStream | null = null

  async function startRecording(): Promise<void> {
    error.value = null
    isPreparing.value = true

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // Prefer webm/opus, fallback to other formats
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/mp4'

      mediaRecorder = new MediaRecorder(stream, { mimeType })
      audioChunks = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data)
        }
      }

      mediaRecorder.start(100) // Collect data every 100ms
      isRecording.value = true
      isPreparing.value = false
    } catch (err) {
      isPreparing.value = false
      const message = err instanceof Error ? err.message : 'Failed to access microphone'
      error.value = message
      console.error('[AudioRecorder] Error:', err)
      throw err
    }
  }

  async function stopRecording(): Promise<File | null> {
    return new Promise((resolve) => {
      if (!mediaRecorder || mediaRecorder.state === 'inactive') {
        isRecording.value = false
        resolve(null)
        return
      }

      mediaRecorder.onstop = () => {
        const mimeType = mediaRecorder?.mimeType || 'audio/webm'
        const blob = new Blob(audioChunks, { type: mimeType })

        // Determine file extension from mime type
        const extension = mimeType.includes('webm') ? 'webm' : 'mp4'
        const fileName = `recording-${Date.now()}.${extension}`

        const file = new File([blob], fileName, { type: mimeType })

        // Clean up
        if (stream) {
          stream.getTracks().forEach(track => track.stop())
          stream = null
        }
        mediaRecorder = null
        audioChunks = []
        isRecording.value = false

        resolve(file)
      }

      mediaRecorder.stop()
    })
  }

  function cancelRecording(): void {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop()
    }
    if (stream) {
      stream.getTracks().forEach(track => track.stop())
      stream = null
    }
    mediaRecorder = null
    audioChunks = []
    isRecording.value = false
    isPreparing.value = false
  }

  // Clean up on unmount
  onUnmounted(() => {
    cancelRecording()
  })

  return {
    isRecording: readonly(isRecording),
    isPreparing: readonly(isPreparing),
    error: readonly(error),
    startRecording,
    stopRecording,
    cancelRecording
  }
}
