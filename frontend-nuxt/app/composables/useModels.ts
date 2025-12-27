export function formatModelName(modelId: string): string {
  // Map of model IDs to display names
  const displayNames: Record<string, string> = {
    'lab-assistant': 'Lab Assistant',
    'google/gemini-2.5-flash-preview-05-20': 'Gemini 2.5 Flash',
    'google/gemini-2.0-flash-exp:free': 'Gemini 2.0 Flash (Free)',
    'anthropic/claude-3.5-sonnet': 'Claude 3.5 Sonnet',
    'openai/gpt-4o-mini': 'GPT-4o Mini',
    'meta-llama/llama-3.3-70b-instruct:free': 'Llama 3.3 70B (Free)'
  }

  if (displayNames[modelId]) {
    return displayNames[modelId]
  }

  // Fallback: format from model ID
  const acronyms = ['gpt']
  const modelName = modelId.split('/')[1] || modelId

  return modelName
    .split('-')
    .map((word) => {
      const lowerWord = word.toLowerCase()
      return acronyms.includes(lowerWord)
        ? word.toUpperCase()
        : word.charAt(0).toUpperCase() + word.slice(1)
    })
    .join(' ')
}

export function useModels() {
  const models = [
    'lab-assistant',
    'google/gemini-2.5-flash-preview-05-20',
    'google/gemini-2.0-flash-exp:free',
    'anthropic/claude-3.5-sonnet',
    'openai/gpt-4o-mini',
    'meta-llama/llama-3.3-70b-instruct:free'
  ]

  const model = useCookie<string>('model', { default: () => 'lab-assistant' })

  return {
    models,
    model,
    formatModelName
  }
}
