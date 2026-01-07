import { getUserSettings } from '../utils/db'

export default defineEventHandler(async (event) => {
  // Get visitor ID from cookie or header (for telegram)
  const visitorId = getCookie(event, 'visitor_id') || getHeader(event, 'x-visitor-id')

  if (!visitorId) {
    // Return defaults if no visitor ID
    return {
      chatModel: 'gemini-3-flash-preview',
      mainThinkingLevel: 'low',
      mediaResolution: 'unspecified',
      preprocessingModel: 'gemini-flash-latest',
      preprocessingThinkingLevel: 'off',
      enableAgentLogging: false
    }
  }

  return await getUserSettings(visitorId)
})
