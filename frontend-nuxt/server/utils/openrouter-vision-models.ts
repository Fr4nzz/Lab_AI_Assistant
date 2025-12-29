/**
 * OpenRouter Free Vision Models Utility
 *
 * Fetches free vision models from OpenRouter API for image analysis tasks.
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
}

interface CachedModels {
  models: string[]
  timestamp: number
}

// Cache for 5 minutes
const CACHE_TTL = 5 * 60 * 1000
let cachedFreeVisionModels: CachedModels | null = null

/**
 * Fetches free vision models from OpenRouter API
 * Models are filtered to only include:
 * - Free models (prompt and completion price = "0")
 * - Vision models (text+image->text modality)
 */
export async function getFreeVisionModels(): Promise<string[]> {
  // Return cached if still valid
  if (cachedFreeVisionModels && Date.now() - cachedFreeVisionModels.timestamp < CACHE_TTL) {
    return cachedFreeVisionModels.models
  }

  try {
    const response = await fetch('https://openrouter.ai/api/v1/models')

    if (!response.ok) {
      console.error('[OpenRouter] Failed to fetch models:', response.status)
      return getDefaultFreeVisionModels()
    }

    const data = await response.json()
    const models: OpenRouterModel[] = data.data || []

    // Filter free vision models
    const freeVisionModels = models
      .filter((model) => {
        // Must be free (both prompt and completion = "0")
        const isFree = model.pricing?.prompt === '0' && model.pricing?.completion === '0'

        // Must be a vision model (text+image->text modality)
        const isVisionModel = model.architecture?.modality === 'text+image->text'

        // Must have :free suffix (OpenRouter convention)
        const hasFreeTag = model.id.endsWith(':free')

        return isFree && isVisionModel && hasFreeTag
      })
      .map(model => model.id)

    console.log(`[OpenRouter] Found ${freeVisionModels.length} free vision models`)

    // Cache the results
    cachedFreeVisionModels = {
      models: freeVisionModels,
      timestamp: Date.now()
    }

    return freeVisionModels
  } catch (error) {
    console.error('[OpenRouter] Error fetching models:', error)
    return getDefaultFreeVisionModels()
  }
}

/**
 * Default fallback vision models if API fetch fails
 */
function getDefaultFreeVisionModels(): string[] {
  return [
    'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-3.2-11b-vision-instruct:free',
    'qwen/qwen2-vl-72b-instruct:free'
  ]
}

/**
 * Gets the best free vision model for rotation detection.
 * Prefers fast, reliable models for simple image analysis.
 */
export async function getBestVisionModel(): Promise<string> {
  const models = await getFreeVisionModels()

  // Prefer these models in order for rotation detection (fast, good vision)
  const preferredOrder = [
    'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-3.2-11b-vision-instruct:free',
    'qwen/qwen2-vl-72b-instruct:free'
  ]

  for (const preferred of preferredOrder) {
    if (models.includes(preferred)) {
      return preferred
    }
  }

  // Return first available free vision model
  return models[0] || 'google/gemini-2.0-flash-exp:free'
}
