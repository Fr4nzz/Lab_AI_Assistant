import { z } from 'zod'
import { getChat, addMessage, updateChatTitle, getLastMessage } from '../../utils/db'
import { getTopFreeModels } from '../../utils/openrouter-models'
import { generateText } from 'ai'
import { createOpenRouter } from '@openrouter/ai-sdk-provider'

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

  if (!config.openrouterApiKey) {
    console.log('[API/chat] No OpenRouter key configured in OPENROUTER_API_KEY env var, skipping title generation')
    console.log('[API/chat] Add your key to frontend-nuxt/.env file')
    return
  }

  console.log('[API/chat] Generating title with OpenRouter...')

  const openrouter = createOpenRouter({
    apiKey: config.openrouterApiKey
  })

  // Prompt with clear instructions and few-shot examples
  const prompt = `Eres un asistente que genera títulos cortos para conversaciones de chat.

REGLAS ESTRICTAS:
- Genera SOLO el título, sin explicaciones
- El título debe tener entre 2-5 palabras en español
- NO uses markdown (**, ##, etc.)
- NO uses comillas ni puntuación especial
- NO empieces con "Título:" ni similar
- El título debe describir el tema principal del mensaje

EJEMPLOS:
Mensaje: "Busca la orden del paciente Juan Pérez"
Título: Búsqueda orden Juan Pérez

Mensaje: "Quiero ver los resultados del hemograma de la orden 12345"
Título: Resultados hemograma

Mensaje: "Necesito agregar un examen de glucosa a la orden existente"
Título: Agregar examen glucosa

Mensaje: "¿Cuáles son los exámenes disponibles para perfil lipídico?"
Título: Exámenes perfil lipídico

Ahora genera un título para este mensaje:
"${messageContent.slice(0, 300)}"

Título:`

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

  const { messages, model, enabledTools, showStats = true } = await readValidatedBody(event, z.object({
    messages: z.array(z.any()),
    model: z.string().optional(),
    enabledTools: z.array(z.string()).optional(),
    showStats: z.boolean().optional()
  }).parse)

  // Get chat to verify it exists
  const chat = await getChat(chatId)
  if (!chat) {
    throw createError({ statusCode: 404, message: 'Chat not found' })
  }

  // Save user message to database BEFORE streaming
  // But check if it's already saved to avoid duplicates (e.g., when regenerate() is called)
  const lastMessage = messages[messages.length - 1]
  if (lastMessage?.role === 'user') {
    const textContent = extractTextContent(lastMessage)

    // Check if this message already exists in DB
    const lastDbMessage = await getLastMessage(chatId)
    const isDuplicate = lastDbMessage?.role === 'user' &&
      lastDbMessage?.content === textContent

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
        showStats
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
  let eventCount = 0
  const eventTypes: Record<string, number> = {}

  const stream = new ReadableStream({
    async start(controller) {
      const decoder = new TextDecoder()

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          controller.enqueue(value)

          // Parse stream to collect text for storage AND debug events
          const text = decoder.decode(value, { stream: true })
          for (const line of text.split('\n')) {
            if (line.startsWith('data: ')) {
              const rawData = line.slice(6)
              eventCount++

              try {
                const parsed = JSON.parse(rawData)
                const eventType = parsed.type || 'unknown'
                eventTypes[eventType] = (eventTypes[eventType] || 0) + 1

                // Log ALL non-text-delta events for debugging
                if (eventType !== 'text-delta') {
                  console.log(`[Stream Event ${eventCount}] ${eventType}:`, JSON.stringify(parsed).slice(0, 200))
                }

                if (parsed.type === 'text-delta' && parsed.delta) {
                  fullResponse += parsed.delta
                }
              } catch {
                // Log non-JSON data (like [DONE])
                if (rawData.trim() && rawData.trim() !== '[DONE]') {
                  console.log(`[Stream Event ${eventCount}] Raw data:`, rawData.slice(0, 100))
                }
              }
            }
          }
        }

        controller.close()

        // Log stream summary
        console.log('[API/chat] Stream complete. Event summary:', eventTypes)
        console.log(`[API/chat] Total events: ${eventCount}`)

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
