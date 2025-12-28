/**
 * OpenRouter Models Utility
 * Fetches and caches free models from OpenRouter official API
 * https://openrouter.ai/docs/api/api-reference/models/get-models
 */

interface OpenRouterModel {
  id: string
  name: string
  pricing: {
    prompt: string
    completion: string
  }
  architecture?: {
    input_modalities?: string[]
    output_modalities?: string[]
  }
  context_length: number
}

interface ModelsCache {
  modelIds: string[]
  fetchedAt: number
}

// Cache models for 1 hour
const CACHE_TTL_MS = 60 * 60 * 1000
let modelsCache: ModelsCache | null = null

/**
 * Fetch models from OpenRouter official API
 */
async function fetchModels(apiKey: string): Promise<OpenRouterModel[]> {
  const response = await fetch('https://openrouter.ai/api/v1/models', {
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    }
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch models: ${response.status}`)
  }

  const data = await response.json()
  return data.data || []
}

/**
 * Filter for free text-capable models
 */
function filterFreeTextModels(models: OpenRouterModel[]): string[] {
  return models
    .filter(model => {
      // Check if it's free (pricing is 0)
      const promptPrice = parseFloat(model.pricing?.prompt || '1')
      const completionPrice = parseFloat(model.pricing?.completion || '1')
      const isFree = promptPrice === 0 && completionPrice === 0

      // Check if it supports text input and output
      const inputModalities = model.architecture?.input_modalities || []
      const outputModalities = model.architecture?.output_modalities || []
      const supportsText = inputModalities.includes('text') && outputModalities.includes('text')

      return isFree && supportsText
    })
    .map(model => model.id)
}

/**
 * Get top N free models from OpenRouter
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
    console.log('[OpenRouter] Fetching free models from official API...')
    const allModels = await fetchModels(apiKey)
    const freeTextModelIds = filterFreeTextModels(allModels)

    console.log(`[OpenRouter] Found ${freeTextModelIds.length} free text models`)

    // Cache the results
    modelsCache = {
      modelIds: freeTextModelIds,
      fetchedAt: now
    }

    const topModels = freeTextModelIds.slice(0, count)
    console.log('[OpenRouter] Top free models:', topModels)

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
      'google/gemma-3-4b-it:free',
      'mistralai/mistral-small-3.1-24b-instruct-2503:free',
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
