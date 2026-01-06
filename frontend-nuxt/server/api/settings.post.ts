import { updateUserSettings } from '../utils/db'

interface SettingsUpdateBody {
  chatModel?: string
  preprocessingModel?: string
  thinkingLevel?: string
}

// Valid options
const VALID_CHAT_MODELS = ['gemini-3-flash-preview', 'gemini-flash-latest']
const VALID_PREPROCESSING_MODELS = ['gemini-flash-lite-latest', 'gemini-flash-latest', 'gemini-3-flash-preview']
const VALID_THINKING_LEVELS = ['none', 'low', 'medium', 'high']

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

  if (body.preprocessingModel && VALID_PREPROCESSING_MODELS.includes(body.preprocessingModel)) {
    updates.preprocessingModel = body.preprocessingModel
  }

  if (body.thinkingLevel && VALID_THINKING_LEVELS.includes(body.thinkingLevel)) {
    updates.thinkingLevel = body.thinkingLevel
  }

  // Update settings
  return await updateUserSettings(visitorId, updates)
})
