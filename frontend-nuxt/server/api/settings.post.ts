import { updateUserSettings } from '../utils/db'

interface SettingsUpdateBody {
  chatModel?: string
  mainThinkingLevel?: string
  preprocessingModel?: string
  preprocessingThinkingLevel?: string
}

// Valid options
const VALID_CHAT_MODELS = ['gemini-3-flash-preview', 'gemini-flash-latest']
const VALID_PREPROCESSING_MODELS = ['gemini-flash-lite-latest', 'gemini-flash-latest', 'gemini-3-flash-preview']

// Thinking levels vary by model
const VALID_GEMINI_3_THINKING_LEVELS = ['minimal', 'low', 'medium', 'high']
const VALID_GEMINI_25_THINKING_LEVELS = ['off', 'dynamic']
const VALID_PREPROCESSING_THINKING_LEVELS = ['none', 'low', 'medium', 'high']

function isValidMainThinkingLevel(level: string, model?: string): boolean {
  // If we know the model, validate against that model's options
  if (model?.includes('gemini-3')) {
    return VALID_GEMINI_3_THINKING_LEVELS.includes(level)
  }
  // For Gemini 2.5 models
  if (model?.includes('gemini-flash') && !model?.includes('gemini-3')) {
    return VALID_GEMINI_25_THINKING_LEVELS.includes(level)
  }
  // If model not specified, accept both
  return [...VALID_GEMINI_3_THINKING_LEVELS, ...VALID_GEMINI_25_THINKING_LEVELS].includes(level)
}

export default defineEventHandler(async (event) => {
  // Get visitor ID from cookie or header (for telegram)
  let visitorId = getCookie(event, 'visitor_id') || getHeader(event, 'x-visitor-id')

  // If no visitor ID, generate one and set cookie
  if (!visitorId) {
    visitorId = crypto.randomUUID()
    setCookie(event, 'visitor_id', visitorId, {
      maxAge: 60 * 60 * 24 * 365, // 1 year
      httpOnly: false, // Allow frontend access
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax'
    })
  }

  const body = await readBody<SettingsUpdateBody>(event)

  // Validate inputs
  const updates: SettingsUpdateBody = {}

  if (body.chatModel && VALID_CHAT_MODELS.includes(body.chatModel)) {
    updates.chatModel = body.chatModel
  }

  if (body.mainThinkingLevel && isValidMainThinkingLevel(body.mainThinkingLevel, body.chatModel || updates.chatModel)) {
    updates.mainThinkingLevel = body.mainThinkingLevel
  }

  if (body.preprocessingModel && VALID_PREPROCESSING_MODELS.includes(body.preprocessingModel)) {
    updates.preprocessingModel = body.preprocessingModel
  }

  if (body.preprocessingThinkingLevel && VALID_PREPROCESSING_THINKING_LEVELS.includes(body.preprocessingThinkingLevel)) {
    updates.preprocessingThinkingLevel = body.preprocessingThinkingLevel
  }

  // Update settings
  return await updateUserSettings(visitorId, updates)
})
