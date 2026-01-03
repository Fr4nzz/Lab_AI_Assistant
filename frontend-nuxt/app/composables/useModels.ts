// Lab Assistant models configuration
// Claude models use Claude Code CLI with Max subscription (no API key needed)
// Gemini models use the backend's API key rotation (fallback)
export interface ModelConfig {
  id: string           // ID sent to backend (also the API model name)
  displayName: string  // Display name in UI
  icon: string         // Icon for the model
  isLabAssistant: boolean // If true, shows Lab Assistant branding
  provider?: 'claude' | 'gemini' // Model provider
}

// Available models configuration
// Claude models are default - use your Max subscription
// Gemini models are fallback when Claude is unavailable
export const MODEL_CONFIGS: ModelConfig[] = [
  {
    id: 'claude-opus-4-5',
    displayName: 'Lab Assistant (Claude Opus 4.5)',
    icon: 'i-lucide-brain',
    isLabAssistant: true,
    provider: 'claude'
  },
  {
    id: 'claude-sonnet-4-5',
    displayName: 'Lab Assistant (Claude Sonnet 4.5)',
    icon: 'i-lucide-zap',
    isLabAssistant: true,
    provider: 'claude'
  },
  {
    id: 'gemini-3-flash-preview',
    displayName: 'Lab Assistant (Gemini 3 Flash)',
    icon: 'i-lucide-flask-conical',
    isLabAssistant: true,
    provider: 'gemini'
  },
  {
    id: 'gemini-flash-latest',
    displayName: 'Lab Assistant (Gemini 2.5 Flash)',
    icon: 'i-lucide-flask-conical',
    isLabAssistant: true,
    provider: 'gemini'
  }
]

export function formatModelName(modelId: string): string {
  const config = MODEL_CONFIGS.find(m => m.id === modelId)
  if (config) return config.displayName

  // Fallback: format from model ID
  const modelName = modelId.split('/')[1] || modelId
  return modelName
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function getModelIcon(modelId: string): string {
  const config = MODEL_CONFIGS.find(m => m.id === modelId)
  return config?.icon || 'i-lucide-bot'
}

export function useModels() {
  // Default to first Lab Assistant model
  const model = useCookie<string>('model', {
    default: () => MODEL_CONFIGS[0]!.id
  })

  const currentModel = computed(() =>
    MODEL_CONFIGS.find(m => m.id === model.value) || MODEL_CONFIGS[0]!
  )

  return {
    models: MODEL_CONFIGS,
    model,
    currentModel,
    formatModelName,
    getModelIcon
  }
}
