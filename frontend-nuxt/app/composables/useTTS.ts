import type { UIMessage } from 'ai'
import { getTextFromMessage } from '@nuxt/ui/utils/ai'

/**
 * Text-to-Speech composable using browser's SpeechSynthesis API
 */
export function useTTS() {
  const isSpeaking = ref(false)
  const currentMessageId = ref<string | null>(null)

  const isSupported = computed(() => {
    return typeof window !== 'undefined' && 'speechSynthesis' in window
  })

  function speak(message: UIMessage, lang = 'es-ES') {
    if (!isSupported.value) return
    stop()

    const text = getTextFromMessage(message)
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang
    utterance.rate = 1.0
    utterance.pitch = 1.0

    utterance.onstart = () => {
      isSpeaking.value = true
      currentMessageId.value = message.id
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

  function isSpeakingMessage(messageId: string): boolean {
    return isSpeaking.value && currentMessageId.value === messageId
  }

  onUnmounted(() => stop())

  return { speak, stop, isSpeaking, isSupported, isSpeakingMessage }
}
