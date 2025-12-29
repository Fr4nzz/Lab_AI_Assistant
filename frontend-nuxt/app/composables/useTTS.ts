/**
 * Text-to-Speech composable using browser's SpeechSynthesis API
 * Inspired by Lobe Chat's TTS implementation
 */
export function useTTS() {
  const isSpeaking = ref(false)
  const currentMessageId = ref<string | null>(null)

  // Check if TTS is supported
  const isSupported = computed(() => {
    return typeof window !== 'undefined' && 'speechSynthesis' in window
  })

  function speak(text: string, messageId?: string, lang = 'es-ES') {
    if (!isSupported.value) return

    // Stop any current speech
    stop()

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang
    utterance.rate = 1.0
    utterance.pitch = 1.0

    utterance.onstart = () => {
      isSpeaking.value = true
      currentMessageId.value = messageId || null
    }

    utterance.onend = () => {
      isSpeaking.value = false
      currentMessageId.value = null
    }

    utterance.onerror = () => {
      isSpeaking.value = false
      currentMessageId.value = null
    }

    speechSynthesis.speak(utterance)
  }

  function stop() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      speechSynthesis.cancel()
    }
    isSpeaking.value = false
    currentMessageId.value = null
  }

  // Check if a specific message is currently being spoken
  function isSpeakingMessage(messageId: string): boolean {
    return isSpeaking.value && currentMessageId.value === messageId
  }

  // Clean up on unmount
  onUnmounted(() => {
    stop()
  })

  return {
    speak,
    stop,
    isSpeaking,
    isSupported,
    isSpeakingMessage,
    currentMessageId
  }
}
