/**
 * OpenRouter Free Vision Models Utility
 *
 * Fetches free vision models from OpenRouter API for image analysis tasks.
 * Models are sorted by: newest first (year/month), then by parameter count (largest first).
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
}

interface CachedModels {
  models: string[]
  timestamp: number
}

// Cache for 5 minutes
const CACHE_TTL = 5 * 60 * 1000
let cachedFreeVisionModels: CachedModels | null = null

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
 * Fetches free vision models from OpenRouter API
 * Models are filtered to only include:
 * - Free models (prompt and completion price = "0")
 * - Vision models (text+image->text modality)
 *
 * Sorted by: newest (year/month) first, then largest (parameter count) first
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

    // Filter and sort free vision models
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

    console.log(`[OpenRouter] Found ${freeVisionModels.length} free vision models (sorted by date/size)`)
    if (freeVisionModels.length > 0) {
      console.log(`[OpenRouter] Top 3 vision models:`, freeVisionModels.slice(0, 3))
    }

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
 * Ordered by newest/largest first
 */
function getDefaultFreeVisionModels(): string[] {
  return [
    'google/gemini-2.0-flash-exp:free',
    'qwen/qwen2-vl-72b-instruct:free',
    'meta-llama/llama-3.2-11b-vision-instruct:free'
  ]
}

/**
 * Gets the best free vision model for rotation detection.
 * Returns the first model from the sorted list (newest + largest).
 */
export async function getBestVisionModel(): Promise<string> {
  const models = await getFreeVisionModels()
  return models[0] || 'google/gemini-2.0-flash-exp:free'
}
