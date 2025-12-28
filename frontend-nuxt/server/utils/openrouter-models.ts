/**
 * OpenRouter Models Utility
 * Fetches and caches free models from OpenRouter API, sorted by latency
 * Uses the frontend API which supports latency-based sorting
 */

interface OpenRouterFrontendModel {
  slug: string
  name: string
  has_text_output: boolean
  input_modalities: string[]
  output_modalities: string[]
}

interface ModelsCache {
  modelIds: string[]
  fetchedAt: number
}

// Cache models for 1 hour
const CACHE_TTL_MS = 60 * 60 * 1000
let modelsCache: ModelsCache | null = null

/**
 * Fetch free models from OpenRouter frontend API, sorted by latency
 * This endpoint returns models pre-sorted by latency (lowest first)
 */
async function fetchFreeModelsByLatency(): Promise<string[]> {
  // Use the frontend API which supports latency sorting
  const url = 'https://openrouter.ai/api/frontend/models?q=free&order=latency-low-to-high'

  const response = await fetch(url, {
    headers: {
      'Accept': 'application/json'
    }
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch models: ${response.status}`)
  }

  const data = await response.json()
  const models: OpenRouterFrontendModel[] = data.data || []

  // Filter for text-capable models only (we need text output for title generation)
  // Also filter out image/video-only models
  const textModels = models.filter(model =>
    model.has_text_output &&
    model.input_modalities?.includes('text') &&
    model.output_modalities?.includes('text')
  )

  // The slug from frontend API needs to be converted to the API model ID format
  // Frontend uses "author/model-name" but for free models we may need ":free" suffix
  return textModels.map(model => {
    // Check if it already has :free suffix
    if (model.slug.includes(':')) {
      return model.slug
    }
    // Add :free suffix for free models
    return `${model.slug}:free`
  })
}

/**
 * Get top N free models from OpenRouter, sorted by latency (fastest first)
 * Results are cached for 1 hour
 */
export async function getTopFreeModels(apiKey: string, count: number = 3): Promise<string[]> {
  const now = Date.now()

  // Return cached models if still valid
  if (modelsCache && (now - modelsCache.fetchedAt) < CACHE_TTL_MS) {
    console.log('[OpenRouter] Using cached models')
    return modelsCache.modelIds.slice(0, count)
  }

  try {
    console.log('[OpenRouter] Fetching free models sorted by latency...')
    const modelIds = await fetchFreeModelsByLatency()

    console.log(`[OpenRouter] Found ${modelIds.length} free text models`)

    // Cache the results
    modelsCache = {
      modelIds,
      fetchedAt: now
    }

    const topModels = modelIds.slice(0, count)
    console.log('[OpenRouter] Top free models (by latency):', topModels)

    return topModels
  } catch (error) {
    console.error('[OpenRouter] Failed to fetch models:', error)

    // Return cached models even if expired, as fallback
    if (modelsCache) {
      console.log('[OpenRouter] Using expired cache as fallback')
      return modelsCache.modelIds.slice(0, count)
    }

    // Ultimate fallback: return known free models
    console.log('[OpenRouter] Using hardcoded fallback models')
    return [
      'mistralai/mistral-small-3.1-24b-instruct-2503:free',
      'google/gemma-3-4b-it:free',
      'deepseek/deepseek-r1-distill-llama-70b:free'
    ]
  }
}

/**
 * Clear the models cache (useful for testing or forcing refresh)
 */
export function clearModelsCache(): void {
  modelsCache = null
}
