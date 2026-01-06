// User settings composable - synced with database
export interface UserSettings {
  chatModel: string
  mainThinkingLevel: string  // For main chat model
  preprocessingModel: string
  preprocessingThinkingLevel: string  // For image preprocessing
}

// Available chat models
export const CHAT_MODELS = [
  { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash', icon: 'i-lucide-flask-conical' },
  { id: 'gemini-flash-latest', name: 'Gemini 2.5 Flash', icon: 'i-lucide-zap' }
]

// Thinking levels for Gemini 3 models (uses thinkingLevel parameter)
export const GEMINI_3_THINKING_LEVELS = [
  { id: 'minimal', name: 'Minimal (fastest)', icon: 'i-lucide-zap' },
  { id: 'low', name: 'Low', icon: 'i-lucide-lightbulb' },
  { id: 'medium', name: 'Medium', icon: 'i-lucide-brain' },
  { id: 'high', name: 'High (most thorough)', icon: 'i-lucide-sparkles' }
]

// Thinking options for Gemini 2.5 models (uses thinkingBudget parameter)
export const GEMINI_25_THINKING_LEVELS = [
  { id: 'off', name: 'Off (no thinking)', icon: 'i-lucide-zap-off', budget: 0 },
  { id: 'dynamic', name: 'Dynamic', icon: 'i-lucide-sparkles', budget: -1 }
]

export const PREPROCESSING_MODELS = [
  { id: 'gemini-flash-lite-latest', name: 'Gemini 2.5 Flash Lite (fastest)', icon: 'i-lucide-zap' },
  { id: 'gemini-flash-latest', name: 'Gemini 2.5 Flash', icon: 'i-lucide-sparkles' },
  { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash (best)', icon: 'i-lucide-brain' }
]

// Thinking levels for preprocessing (simplified)
export const PREPROCESSING_THINKING_LEVELS = [
  { id: 'none', name: 'None (fastest)', icon: 'i-lucide-zap' },
  { id: 'low', name: 'Low (default)', icon: 'i-lucide-lightbulb' },
  { id: 'medium', name: 'Medium', icon: 'i-lucide-brain' },
  { id: 'high', name: 'High (most thorough)', icon: 'i-lucide-sparkles' }
]

const DEFAULT_SETTINGS: UserSettings = {
  chatModel: 'gemini-3-flash-preview',
  mainThinkingLevel: 'low',  // Default for Gemini 3 Flash
  preprocessingModel: 'gemini-flash-lite-latest',
  preprocessingThinkingLevel: 'low'
}

// Helper to check if model is Gemini 3
export function isGemini3Model(modelId: string): boolean {
  return modelId.includes('gemini-3')
}

// Get thinking levels for a specific model
export function getThinkingLevelsForModel(modelId: string) {
  return isGemini3Model(modelId) ? GEMINI_3_THINKING_LEVELS : GEMINI_25_THINKING_LEVELS
}

// Get default thinking level for a model
export function getDefaultThinkingLevel(modelId: string): string {
  return isGemini3Model(modelId) ? 'low' : 'dynamic'
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
        mainThinkingLevel: data.mainThinkingLevel || getDefaultThinkingLevel(data.chatModel || DEFAULT_SETTINGS.chatModel),
        preprocessingModel: data.preprocessingModel || DEFAULT_SETTINGS.preprocessingModel,
        preprocessingThinkingLevel: data.preprocessingThinkingLevel || DEFAULT_SETTINGS.preprocessingThinkingLevel
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
        mainThinkingLevel: data.mainThinkingLevel || settings.value.mainThinkingLevel,
        preprocessingModel: data.preprocessingModel || settings.value.preprocessingModel,
        preprocessingThinkingLevel: data.preprocessingThinkingLevel || settings.value.preprocessingThinkingLevel
      }
      return settings.value
    } catch (error) {
      console.error('Failed to save settings:', error)
      throw error
    }
  }

  // Individual setters (auto-save)
  async function setChatModel(model: string) {
    // When model changes, reset thinking level to default for that model
    const newThinkingLevel = getDefaultThinkingLevel(model)
    settings.value.chatModel = model
    settings.value.mainThinkingLevel = newThinkingLevel
    await saveSettings({ chatModel: model, mainThinkingLevel: newThinkingLevel })
  }

  async function setMainThinkingLevel(level: string) {
    settings.value.mainThinkingLevel = level
    await saveSettings({ mainThinkingLevel: level })
  }

  async function setPreprocessingModel(model: string) {
    settings.value.preprocessingModel = model
    await saveSettings({ preprocessingModel: model })
  }

  async function setPreprocessingThinkingLevel(level: string) {
    settings.value.preprocessingThinkingLevel = level
    await saveSettings({ preprocessingThinkingLevel: level })
  }

  // Computed helpers
  const currentChatModel = computed(() =>
    CHAT_MODELS.find(m => m.id === settings.value.chatModel) || CHAT_MODELS[0]
  )

  // Thinking levels for current model
  const availableThinkingLevels = computed(() =>
    getThinkingLevelsForModel(settings.value.chatModel)
  )

  const currentMainThinkingLevel = computed(() => {
    const levels = getThinkingLevelsForModel(settings.value.chatModel)
    return levels.find(l => l.id === settings.value.mainThinkingLevel) || levels[0]
  })

  const currentPreprocessingModel = computed(() =>
    PREPROCESSING_MODELS.find(m => m.id === settings.value.preprocessingModel) || PREPROCESSING_MODELS[0]
  )

  const currentPreprocessingThinkingLevel = computed(() =>
    PREPROCESSING_THINKING_LEVELS.find(l => l.id === settings.value.preprocessingThinkingLevel) || PREPROCESSING_THINKING_LEVELS[1]
  )

  return {
    settings,
    isLoading,
    isLoaded,
    visitorId,
    loadSettings,
    saveSettings,
    setChatModel,
    setMainThinkingLevel,
    setPreprocessingModel,
    setPreprocessingThinkingLevel,
    currentChatModel,
    availableThinkingLevels,
    currentMainThinkingLevel,
    currentPreprocessingModel,
    currentPreprocessingThinkingLevel,
    isGemini3Model,
    getThinkingLevelsForModel,
    getDefaultThinkingLevel,
    CHAT_MODELS,
    PREPROCESSING_MODELS,
    PREPROCESSING_THINKING_LEVELS,
    GEMINI_3_THINKING_LEVELS,
    GEMINI_25_THINKING_LEVELS
  }
}
