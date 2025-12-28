/**
 * OpenRouter Vision Models Utility
 * Fetches and caches free vision models from OpenRouter official API
 * Uses the same approach as openrouter-models.ts for reliability
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

interface VisionModelsCache {
  modelIds: string[]
  fetchedAt: number
}

// Cache models for 1 hour
const CACHE_TTL_MS = 60 * 60 * 1000
let visionModelsCache: VisionModelsCache | null = null

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
 * Filter for free vision models (models that can process images and output text)
 */
function filterFreeVisionModels(models: OpenRouterModel[]): string[] {
  return models
    .filter(model => {
      // Check if it's free (pricing is 0)
      const promptPrice = parseFloat(model.pricing?.prompt || '1')
      const completionPrice = parseFloat(model.pricing?.completion || '1')
      const isFree = promptPrice === 0 && completionPrice === 0

      // Check if it supports image input and text output
      const inputModalities = model.architecture?.input_modalities || []
      const outputModalities = model.architecture?.output_modalities || []
      const supportsVision = inputModalities.includes('image') && outputModalities.includes('text')

      return isFree && supportsVision
    })
    .map(model => model.id)
}

/**
 * Get top N free vision models from OpenRouter
 * Results are cached for 1 hour
 */
export async function getTopFreeVisionModels(apiKey: string, count: number = 3): Promise<string[]> {
  const now = Date.now()

  // Return cached models if still valid
  if (visionModelsCache && (now - visionModelsCache.fetchedAt) < CACHE_TTL_MS) {
    console.log('[OpenRouter] Using cached vision models')
    return visionModelsCache.modelIds.slice(0, count)
  }

  try {
    console.log('[OpenRouter] Fetching free vision models from official API...')
    const allModels = await fetchModels(apiKey)
    const freeVisionModelIds = filterFreeVisionModels(allModels)

    console.log(`[OpenRouter] Found ${freeVisionModelIds.length} free vision models`)

    // Cache the results
    visionModelsCache = {
      modelIds: freeVisionModelIds,
      fetchedAt: now
    }

    const topModels = freeVisionModelIds.slice(0, count)
    console.log('[OpenRouter] Top free vision models:', topModels)

    return topModels
  } catch (error) {
    console.error('[OpenRouter] Failed to fetch vision models:', error)

    // Return cached models even if expired, as fallback
    if (visionModelsCache) {
      console.log('[OpenRouter] Using expired cache as fallback')
      return visionModelsCache.modelIds.slice(0, count)
    }

    // Ultimate fallback: return known free vision models
    console.log('[OpenRouter] Using hardcoded fallback vision models')
    return [
      'google/gemini-2.0-flash-exp:free',
      'google/gemma-3-27b-it:free',
      'meta-llama/llama-4-maverick:free'
    ]
  }
}

/**
 * Clear the vision models cache (useful for testing or forcing refresh)
 */
export function clearVisionModelsCache(): void {
  visionModelsCache = null
}
