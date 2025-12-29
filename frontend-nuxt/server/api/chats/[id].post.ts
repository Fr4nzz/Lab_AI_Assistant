import { z } from 'zod'
import { getChat, addMessage, updateChatTitle, getLastMessage } from '../../utils/db'
import { getTopFreeModels } from '../../utils/openrouter-models'
import { generateText } from 'ai'
import { createOpenRouter } from '@openrouter/ai-sdk-provider'

// Startup validation - warn if API key not configured
const startupConfig = useRuntimeConfig()
if (!startupConfig.openrouterApiKey) {
  console.warn('[API/chat] WARNING: OPENROUTER_API_KEY not configured - title generation will be disabled')
  console.warn('[API/chat] Add OPENROUTER_API_KEY to frontend-nuxt/.env to enable auto-generated chat titles')
}

defineRouteMeta({
  openAPI: {
    description: 'Send message to AI and stream response.',
    tags: ['chat']
  }
})

// Clean up generated title text
function cleanTitle(text: string): string {
  let title = text.trim()
    .replace(/^\*\*|\*\*$/g, '') // Remove bold markdown
    .replace(/^#+\s*/, '') // Remove heading markdown
    .replace(/^["']|["']$/g, '') // Remove quotes
    .replace(/^Título:\s*/i, '') // Remove "Título:" prefix
    .replace(/\n.*/g, '') // Take only first line
    .trim()

  // Limit length
  if (title.length > 50) {
    title = title.substring(0, 47) + '...'
  }

  return title
}

// Generate title for a chat using dynamic free models with fallback
async function generateTitle(chatId: string, messageContent: string): Promise<void> {
  const config = useRuntimeConfig()

  console.log('[API/chat] generateTitle called for chatId:', chatId)
  console.log('[API/chat] openrouterApiKey configured:', !!config.openrouterApiKey, config.openrouterApiKey ? `(${config.openrouterApiKey.slice(0, 10)}...)` : '')

  if (!config.openrouterApiKey) {
    console.log('[API/chat] No OpenRouter key configured in OPENROUTER_API_KEY env var, skipping title generation')
    console.log('[API/chat] Add your key to frontend-nuxt/.env file')
    return
  }

  console.log('[API/chat] Generating title with OpenRouter...')

  const openrouter = createOpenRouter({
    apiKey: config.openrouterApiKey
  })

  // Prompt based on Lobe Chat's approach - simple and direct
  const prompt = `You are a professional conversation summarizer. Generate a concise title that captures the essence of the conversation.

Rules:
- Output ONLY the title text, no explanations or additional context
- Maximum 5 words
- Maximum 50 characters
- No punctuation marks
- Use the language: Spanish
- The title should accurately reflect the main topic
- Keep it short and to the point

Conversation message:
"${messageContent.slice(0, 300)}"

Title:`

  // Get top 3 free models dynamically
  const freeModels = await getTopFreeModels(config.openrouterApiKey, 3)
  console.log('[API/chat] Available free models for title:', freeModels)

  // Try each model with fallback, using latency-based provider sorting
  for (const modelId of freeModels) {
    try {
      console.log(`[API/chat] Trying model: ${modelId}`)

      // Use extraBody to pass provider.sort for latency optimization
      // https://openrouter.ai/docs/guides/routing/provider-selection
      const model = openrouter(modelId, {
        extraBody: {
          provider: {
            sort: 'latency'
          }
        }
      })

      const { text } = await generateText({
        model,
        prompt,
        temperature: 0.3,
        maxTokens: 20
      })

      const title = cleanTitle(text)

      if (title && title !== 'Nuevo Chat' && title.length > 0) {
        await updateChatTitle(chatId, title)
        console.log('[API/chat] Generated title:', title)
        return // Success, exit
      }
    } catch (error) {
      console.warn(`[API/chat] Model ${modelId} failed:`, (error as Error).message)
      // Continue to next model
    }
  }

  console.error('[API/chat] All models failed to generate title')
}

// Extract text content from message
function extractTextContent(message: any): string {
  if (typeof message.content === 'string') return message.content
  if (message.parts) {
    return message.parts
      .filter((p: any) => p.type === 'text')
      .map((p: any) => p.text)
      .join('')
  }
  return ''
}

// Convert messages for backend (handle multimodal)
function convertMessagesForBackend(messages: any[]) {
  return messages.map(msg => {
    if (typeof msg.content === 'string') {
      return { role: msg.role, content: msg.content }
    }

    if (msg.parts) {
      const hasMedia = msg.parts.some((p: any) =>
        ['file', 'image', 'audio'].includes(p.type)
      )

      if (hasMedia) {
        const content = msg.parts.map((part: any) => {
          if (part.type === 'text') return { type: 'text', text: part.text }
          if (part.mimeType?.startsWith('audio/') || part.mimeType?.startsWith('video/')) {
            return { type: 'media', data: part.data, mime_type: part.mimeType }
          }
          if (part.url) {
            return { type: 'image_url', image_url: { url: part.url } }
          }
          if (part.data && part.mimeType) {
            return { type: 'image_url', image_url: { url: `data:${part.mimeType};base64,${part.data}` } }
          }
          return null
        }).filter(Boolean)

        return { role: msg.role, content }
      }

      const textContent = msg.parts
        .filter((p: any) => p.type === 'text')
        .map((p: any) => p.text)
        .join('')
      return { role: msg.role, content: textContent }
    }

    return { role: msg.role, content: '' }
  })
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const session = await getUserSession(event)

  const { id: chatId } = await getValidatedRouterParams(event, z.object({
    id: z.string()
  }).parse)

  const { messages, model, enabledTools, showStats = true, rotationResults } = await readValidatedBody(event, z.object({
    messages: z.array(z.any()),
    model: z.string().optional(),
    enabledTools: z.array(z.string()).optional(),
    showStats: z.boolean().optional(),
    rotationResults: z.array(z.object({
      fileName: z.string(),
      rotation: z.number(),
      model: z.string().nullable(),
      timing: z.object({
        modelMs: z.number().optional(),
        totalMs: z.number().optional()
      }).optional(),
      rotatedUrl: z.string(),
      state: z.string()
    })).optional()
  }).parse)

  // DEBUG: Log received rotation results
  console.log(`[API/chat] Received request for chat ${chatId}:`)
  console.log(`[API/chat]   - messages: ${messages.length}`)
  console.log(`[API/chat]   - rotationResults: ${rotationResults?.length || 0}`, rotationResults ? JSON.stringify(rotationResults.map(r => ({ fileName: r.fileName, rotation: r.rotation }))) : 'none')

  // Get chat to verify it exists
  const chat = await getChat(chatId)
  if (!chat) {
    throw createError({ statusCode: 404, message: 'Chat not found' })
  }

  // Save user message to database BEFORE streaming
  // But check if it's already saved to avoid duplicates (e.g., when regenerate() is called)
  const lastMessage = messages[messages.length - 1]
  console.log(`[API/chat] Last message role: ${lastMessage?.role}`)

  if (lastMessage?.role === 'user') {
    const textContent = extractTextContent(lastMessage)
    console.log(`[API/chat] User message text: "${textContent.slice(0, 50)}..."`)

    // Check if this message already exists in DB
    const lastDbMessage = await getLastMessage(chatId)
    const isDuplicate = lastDbMessage?.role === 'user' &&
      lastDbMessage?.content === textContent
    console.log(`[API/chat] Is duplicate: ${isDuplicate}, lastDbMessage role: ${lastDbMessage?.role}`)

    if (!isDuplicate) {
      await addMessage({
        chatId,
        role: 'user',
        content: textContent,
        parts: lastMessage.parts
      })

      // Generate title for new chats (fire and forget)
      console.log(`[API/chat] Chat title check - current title: "${chat.title}", type: ${typeof chat.title}`)
      const needsTitle = !chat.title || chat.title === 'Nuevo Chat' || chat.title.trim() === ''
      console.log(`[API/chat] Needs title generation: ${needsTitle}`)
      if (needsTitle) {
        console.log('[API/chat] Triggering title generation...')
        generateTitle(chatId, textContent).catch((err) => {
          console.error('[API/chat] Title generation error:', err)
        })
      }
    } else {
      console.log('[API/chat] Skipping message save and title gen - duplicate detected')
    }
  }

  // Convert messages to backend format (multimodal support)
  const backendMessages = convertMessagesForBackend(messages)

  // Proxy to Python backend
  const backendUrl = config.backendUrl || 'http://localhost:8000'

  console.log(`[API/chat] Proxying to backend: ${backendUrl}/api/chat/aisdk`)

  let response: Response
  try {
    response = await fetch(`${backendUrl}/api/chat/aisdk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: backendMessages,
        chatId,
        model: model || 'lab-assistant',
        tools: enabledTools,
        showStats,
        rotationResults: rotationResults || undefined
      })
    })
  } catch (error) {
    console.error('[API/chat] Backend connection error:', error)
    throw createError({
      statusCode: 503,
      message: 'Backend not available. Please try again.'
    })
  }

  if (!response.ok || !response.body) {
    console.error('[API/chat] Backend error:', response.status)
    throw createError({
      statusCode: response.status,
      message: 'Backend error'
    })
  }

  // Collect response while streaming for database storage
  const reader = response.body.getReader()
  let fullResponse = ''

  const stream = new ReadableStream({
    async start(controller) {
      const decoder = new TextDecoder()

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          controller.enqueue(value)

          // Parse stream to collect text for storage
          const text = decoder.decode(value, { stream: true })
          for (const line of text.split('\n')) {
            if (line.startsWith('data: ')) {
              try {
                const parsed = JSON.parse(line.slice(6))
                if (parsed.type === 'text-delta' && parsed.delta) {
                  fullResponse += parsed.delta
                }
              } catch {
                // Skip non-JSON lines
              }
            }
          }
        }

        controller.close()

        // Save assistant response to database
        if (fullResponse) {
          await addMessage({
            chatId,
            role: 'assistant',
            content: fullResponse
          })
          console.log('[API/chat] Saved assistant response, length:', fullResponse.length)
        }
      } catch (error) {
        console.error('[API/chat] Stream error:', error)
        controller.error(error)
      }
    }
  })

  // Return stream with AI SDK headers
  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'x-vercel-ai-ui-message-stream': 'v1',
      'X-Chat-Id': chatId,
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    }
  })
})
