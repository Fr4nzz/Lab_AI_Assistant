// User settings composable - synced with database
export interface UserSettings {
  chatModel: string
  preprocessingModel: string
  thinkingLevel: string
}

// Available options
export const CHAT_MODELS = [
  { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash', icon: 'i-lucide-flask-conical' },
  { id: 'gemini-flash-latest', name: 'Gemini 2.5 Flash', icon: 'i-lucide-zap' }
]

export const PREPROCESSING_MODELS = [
  { id: 'gemini-flash-lite-latest', name: 'Gemini 2.5 Flash Lite (fastest)', icon: 'i-lucide-zap' },
  { id: 'gemini-flash-latest', name: 'Gemini 2.5 Flash', icon: 'i-lucide-sparkles' },
  { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash (best)', icon: 'i-lucide-brain' }
]

export const THINKING_LEVELS = [
  { id: 'none', name: 'None (fastest)', icon: 'i-lucide-zap' },
  { id: 'low', name: 'Low (default)', icon: 'i-lucide-lightbulb' },
  { id: 'medium', name: 'Medium', icon: 'i-lucide-brain' },
  { id: 'high', name: 'High (most thorough)', icon: 'i-lucide-sparkles' }
]

const DEFAULT_SETTINGS: UserSettings = {
  chatModel: 'gemini-3-flash-preview',
  preprocessingModel: 'gemini-flash-lite-latest',
  thinkingLevel: 'low'
}

export function useSettings() {
  // Global state
  const settings = useState<UserSettings>('userSettings', () => ({ ...DEFAULT_SETTINGS }))
  const isLoading = useState<boolean>('settingsLoading', () => false)
  const isLoaded = useState<boolean>('settingsLoaded', () => false)

  // Ensure visitor ID cookie exists
  const visitorId = useCookie('visitor_id', {
    default: () => crypto.randomUUID(),
    maxAge: 60 * 60 * 24 * 365 // 1 year
  })

  // Load settings from API
  async function loadSettings() {
    if (isLoaded.value) return settings.value

    isLoading.value = true
    try {
      const data = await $fetch<UserSettings>('/api/settings')
      settings.value = {
        chatModel: data.chatModel || DEFAULT_SETTINGS.chatModel,
        preprocessingModel: data.preprocessingModel || DEFAULT_SETTINGS.preprocessingModel,
        thinkingLevel: data.thinkingLevel || DEFAULT_SETTINGS.thinkingLevel
      }
      isLoaded.value = true
    } catch (error) {
      console.error('Failed to load settings:', error)
      settings.value = { ...DEFAULT_SETTINGS }
    } finally {
      isLoading.value = false
    }

    return settings.value
  }

  // Save settings to API
  async function saveSettings(updates: Partial<UserSettings>) {
    try {
      const data = await $fetch<UserSettings>('/api/settings', {
        method: 'POST',
        body: updates
      })
      settings.value = {
        chatModel: data.chatModel || settings.value.chatModel,
        preprocessingModel: data.preprocessingModel || settings.value.preprocessingModel,
        thinkingLevel: data.thinkingLevel || settings.value.thinkingLevel
      }
      return settings.value
    } catch (error) {
      console.error('Failed to save settings:', error)
      throw error
    }
  }

  // Individual setters (auto-save)
  async function setChatModel(model: string) {
    settings.value.chatModel = model
    await saveSettings({ chatModel: model })
  }

  async function setPreprocessingModel(model: string) {
    settings.value.preprocessingModel = model
    await saveSettings({ preprocessingModel: model })
  }

  async function setThinkingLevel(level: string) {
    settings.value.thinkingLevel = level
    await saveSettings({ thinkingLevel: level })
  }

  // Computed helpers
  const currentChatModel = computed(() =>
    CHAT_MODELS.find(m => m.id === settings.value.chatModel) || CHAT_MODELS[0]
  )

  const currentPreprocessingModel = computed(() =>
    PREPROCESSING_MODELS.find(m => m.id === settings.value.preprocessingModel) || PREPROCESSING_MODELS[0]
  )

  const currentThinkingLevel = computed(() =>
    THINKING_LEVELS.find(l => l.id === settings.value.thinkingLevel) || THINKING_LEVELS[1]
  )

  return {
    settings,
    isLoading,
    isLoaded,
    visitorId,
    loadSettings,
    saveSettings,
    setChatModel,
    setPreprocessingModel,
    setThinkingLevel,
    currentChatModel,
    currentPreprocessingModel,
    currentThinkingLevel,
    CHAT_MODELS,
    PREPROCESSING_MODELS,
    THINKING_LEVELS
  }
}
