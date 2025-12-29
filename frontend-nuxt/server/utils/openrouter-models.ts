/**
 * OpenRouter Free Models Utility
 *
 * Fetches free text models from OpenRouter API.
 * Models are sorted by: newest first (year/month), then by parameter count (largest first).
 * Uses OpenRouter's official endpoint: https://openrouter.ai/api/v1/models
 */

interface OpenRouterModel {
  id: string
  name: string
  created: number // Unix timestamp
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
 * Extracts year and month from a Unix timestamp.
 * Returns a comparable number: YYYYMM (e.g., 202501 for January 2025)
 */
function getYearMonth(timestamp: number): number {
  const date = new Date(timestamp * 1000)
  return date.getFullYear() * 100 + (date.getMonth() + 1)
}

/**
 * Extracts parameter count from model ID or name.
 * Parses patterns like "70b", "8b", "3.1-24b", "72b", etc.
 * Returns the number in billions, or 0 if not found.
 */
function extractParameterCount(modelId: string): number {
  // Match patterns like: 70b, 8b, 24b, 7b, 1.5b, etc.
  // Look for number followed by 'b' (case insensitive)
  const match = modelId.toLowerCase().match(/(\d+(?:\.\d+)?)\s*b(?:[^a-z]|$)/i)
  if (match) {
    return parseFloat(match[1])
  }
  return 0
}

/**
 * Fetches free text models from OpenRouter API
 * Models are filtered to only include:
 * - Free models (prompt and completion price = "0")
 * - Text models (not image/audio generation)
 * - Models with :free suffix in their ID
 *
 * Sorted by: newest (year/month) first, then largest (parameter count) first
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

    // Filter and sort free text models
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
      .sort((a, b) => {
        // Sort by year/month (newest first)
        const yearMonthA = getYearMonth(a.created || 0)
        const yearMonthB = getYearMonth(b.created || 0)

        if (yearMonthB !== yearMonthA) {
          return yearMonthB - yearMonthA // Newest first
        }

        // Same year/month: sort by parameter count (largest first)
        const paramsA = extractParameterCount(a.id)
        const paramsB = extractParameterCount(b.id)
        return paramsB - paramsA // Largest first
      })
      .map(model => model.id)

    console.log(`[OpenRouter] Found ${freeTextModels.length} free text models (sorted by date/size)`)
    if (freeTextModels.length > 0) {
      console.log(`[OpenRouter] Top 3 text models:`, freeTextModels.slice(0, 3))
    }

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
 * Default fallback models if API fetch fails
 * Ordered by newest/largest first
 */
function getDefaultFreeModels(): string[] {
  return [
    'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'qwen/qwen-2.5-72b-instruct:free',
    'mistralai/mistral-small-3.1-24b-instruct-2503:free'
  ]
}

/**
 * Gets the best free model for title generation.
 * Returns the first model from the sorted list (newest + largest).
 */
export async function getBestTitleModel(): Promise<string> {
  const models = await getFreeTextModels()
  return models[0] || 'google/gemini-2.0-flash-exp:free'
}
