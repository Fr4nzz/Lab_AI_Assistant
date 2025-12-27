/**
 * Available AI models for the Lab Assistant
 * Models are accessed via OpenRouter
 */

export interface ModelConfig {
  id: string;
  name: string;
  provider: string;
  free: boolean;
  description?: string;
}

export const AVAILABLE_MODELS: ModelConfig[] = [
  {
    id: 'google/gemini-2.5-flash-preview-05-20',
    name: 'Gemini 2.5 Flash',
    provider: 'Google',
    free: false,
    description: 'Fast and capable multimodal model'
  },
  {
    id: 'google/gemini-2.0-flash-exp:free',
    name: 'Gemini 2.0 Flash (Free)',
    provider: 'Google',
    free: true,
    description: 'Free tier with rate limits'
  },
  {
    id: 'anthropic/claude-3.5-sonnet',
    name: 'Claude 3.5 Sonnet',
    provider: 'Anthropic',
    free: false,
    description: 'Excellent reasoning and code'
  },
  {
    id: 'meta-llama/llama-3.3-70b-instruct:free',
    name: 'Llama 3.3 70B (Free)',
    provider: 'Meta',
    free: true,
    description: 'Open source, good for general tasks'
  },
  {
    id: 'openai/gpt-4o-mini',
    name: 'GPT-4o Mini',
    provider: 'OpenAI',
    free: false,
    description: 'Fast and affordable GPT-4'
  },
] as const;

export type ModelId = typeof AVAILABLE_MODELS[number]['id'];

export const DEFAULT_MODEL: ModelId = 'google/gemini-2.5-flash-preview-05-20';

/**
 * Get model config by ID
 */
export function getModelById(id: string): ModelConfig | undefined {
  return AVAILABLE_MODELS.find(m => m.id === id);
}
