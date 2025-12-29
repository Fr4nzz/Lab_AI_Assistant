/**
 * OpenRouter Free Models Utility
 *
 * Fetches free text models from OpenRouter API and provides latency-sorted access.
 * Uses OpenRouter's official endpoint: https://openrouter.ai/api/v1/models
 */

interface OpenRouterModel {
  id: string
  name: string
  pricing: {
    prompt: string
    completion: string
  }
  context_length: number
  architecture: {
    modality: string
    tokenizer: string
    instruct_type?: string
  }
  top_provider?: {
    is_moderated: boolean
    context_length?: number
    max_completion_tokens?: number
  }
  per_request_limits?: {
    prompt_tokens: string
    completion_tokens: string
  }
}

interface CachedModels {
  models: string[]
  timestamp: number
}

// Cache for 5 minutes
const CACHE_TTL = 5 * 60 * 1000
let cachedFreeTextModels: CachedModels | null = null

/**
 * Fetches free text models from OpenRouter API
 * Models are filtered to only include:
 * - Free models (prompt and completion price = "0")
 * - Text models (not image/audio generation)
 * - Models with :free suffix in their ID
 */
export async function getFreeTextModels(): Promise<string[]> {
  // Return cached if still valid
  if (cachedFreeTextModels && Date.now() - cachedFreeTextModels.timestamp < CACHE_TTL) {
    return cachedFreeTextModels.models
  }

  try {
    const response = await fetch('https://openrouter.ai/api/v1/models')

    if (!response.ok) {
      console.error('[OpenRouter] Failed to fetch models:', response.status)
      return getDefaultFreeModels()
    }

    const data = await response.json()
    const models: OpenRouterModel[] = data.data || []

    // Filter free text models
    const freeTextModels = models
      .filter((model) => {
        // Must be free (both prompt and completion = "0")
        const isFree = model.pricing?.prompt === '0' && model.pricing?.completion === '0'

        // Must be a text model (text-to-text modality)
        const isTextModel = model.architecture?.modality === 'text->text' ||
                           model.architecture?.modality === 'text+image->text'

        // Must have :free suffix (OpenRouter convention)
        const hasFreeTag = model.id.endsWith(':free')

        return isFree && isTextModel && hasFreeTag
      })
      .map(model => model.id)

    console.log(`[OpenRouter] Found ${freeTextModels.length} free text models`)

    // Cache the results
    cachedFreeTextModels = {
      models: freeTextModels,
      timestamp: Date.now()
    }

    return freeTextModels
  } catch (error) {
    console.error('[OpenRouter] Error fetching models:', error)
    return getDefaultFreeModels()
  }
}

/**
 * Gets the extra body params for OpenRouter with latency-based provider sorting.
 * This tells OpenRouter to prefer providers with lowest latency.
 *
 * @see https://openrouter.ai/docs/features/provider-routing
 */
export function getLatencySortedProviderBody() {
  return {
    provider: {
      sort: 'latency'
    }
  }
}

/**
 * Default fallback models if API fetch fails
 */
function getDefaultFreeModels(): string[] {
  return [
    'mistralai/mistral-small-3.1-24b-instruct-2503:free',
    'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'qwen/qwen-2.5-72b-instruct:free'
  ]
}

/**
 * Gets the best free model for title generation.
 * Prefers smaller, faster models for quick title generation.
 */
export async function getBestTitleModel(): Promise<string> {
  const models = await getFreeTextModels()

  // Prefer these models in order for title generation (small, fast, good quality)
  const preferredOrder = [
    'mistralai/mistral-small-3.1-24b-instruct-2503:free',
    'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-3.3-70b-instruct:free'
  ]

  for (const preferred of preferredOrder) {
    if (models.includes(preferred)) {
      return preferred
    }
  }

  // Return first available free model
  return models[0] || 'mistralai/mistral-small-3.1-24b-instruct-2503:free'
}
