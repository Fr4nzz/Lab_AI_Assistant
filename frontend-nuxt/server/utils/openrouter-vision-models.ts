/**
 * OpenRouter Vision Models Utility
 * Fetches and caches free vision models (models that can process images)
 * Uses the frontend API which supports filtering by input modality and top-weekly sorting
 */

interface OpenRouterFrontendModel {
  slug: string
  name: string
  has_text_output: boolean
  input_modalities: string[]
  output_modalities: string[]
}

interface VisionModelsCache {
  modelIds: string[]
  fetchedAt: number
}

// Cache models for 1 hour
const CACHE_TTL_MS = 60 * 60 * 1000
let visionModelsCache: VisionModelsCache | null = null

/**
 * Fetch free vision models from OpenRouter frontend API, sorted by top-weekly popularity
 */
async function fetchFreeVisionModels(): Promise<string[]> {
  // Use the frontend API which supports input_modalities filter and top-weekly sorting
  const url = 'https://openrouter.ai/api/frontend/models?input_modalities=image&order=top-weekly&q=free'

  const response = await fetch(url, {
    headers: {
      'Accept': 'application/json'
    }
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch vision models: ${response.status}`)
  }

  const data = await response.json()
  const models: OpenRouterFrontendModel[] = data.data || []

  // Filter for models that:
  // 1. Can process images (input_modalities includes 'image')
  // 2. Output text (has_text_output is true) - we need text responses for rotation detection
  // 3. Not image generation models
  const visionModels = models.filter(model =>
    model.has_text_output &&
    model.input_modalities?.includes('image') &&
    model.input_modalities?.includes('text') &&
    model.output_modalities?.includes('text')
  )

  // Return model IDs with :free suffix if needed
  return visionModels.map(model => {
    if (model.slug.includes(':')) {
      return model.slug
    }
    return `${model.slug}:free`
  })
}

/**
 * Get top N free vision models from OpenRouter, sorted by popularity
 * Results are cached for 1 hour
 */
export async function getTopFreeVisionModels(count: number = 3): Promise<string[]> {
  const now = Date.now()

  // Return cached models if still valid
  if (visionModelsCache && (now - visionModelsCache.fetchedAt) < CACHE_TTL_MS) {
    console.log('[OpenRouter] Using cached vision models')
    return visionModelsCache.modelIds.slice(0, count)
  }

  try {
    console.log('[OpenRouter] Fetching free vision models sorted by top-weekly...')
    const modelIds = await fetchFreeVisionModels()

    console.log(`[OpenRouter] Found ${modelIds.length} free vision models`)

    // Cache the results
    visionModelsCache = {
      modelIds,
      fetchedAt: now
    }

    const topModels = modelIds.slice(0, count)
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
