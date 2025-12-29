// Lab Assistant models configuration
// These models use the backend's Gemini integration with tools
export interface ModelConfig {
  id: string           // ID sent to backend (also the API model name)
  displayName: string  // Display name in UI
  icon: string         // Icon for the model
  isLabAssistant: boolean // If true, shows Lab Assistant branding
}

// Available models configuration
// Lab Assistant models use Gemini via the backend with tools
// Non-Lab Assistant models could use OpenRouter directly (future)
export const MODEL_CONFIGS: ModelConfig[] = [
  {
    id: 'gemini-2.5-flash-preview-05-20',
    displayName: 'Lab Assistant (Gemini 2.5 Flash)',
    icon: 'i-lucide-flask-conical',
    isLabAssistant: true
  },
  {
    id: 'gemini-2.0-flash',
    displayName: 'Lab Assistant (Gemini 2.0 Flash)',
    icon: 'i-lucide-flask-conical',
    isLabAssistant: true
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
