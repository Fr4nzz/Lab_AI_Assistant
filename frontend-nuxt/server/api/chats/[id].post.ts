import { z } from 'zod'
import { getChat, addMessage, updateChatTitle } from '../../utils/db'
import { generateText } from 'ai'
import { createOpenRouter } from '@openrouter/ai-sdk-provider'

defineRouteMeta({
  openAPI: {
    description: 'Send message to AI and stream response.',
    tags: ['chat']
  }
})

// Generate title for a chat
async function generateTitle(chatId: string, messageContent: string): Promise<void> {
  const config = useRuntimeConfig()

  if (!config.openrouterApiKey) {
    console.log('[API/chat] No OpenRouter key, skipping title generation')
    return
  }

  try {
    const openrouter = createOpenRouter({
      apiKey: config.openrouterApiKey
    })

    const { text } = await generateText({
      model: openrouter('nvidia/nemotron-3-nano-30b-a3b:free'),
      prompt: `Generate a very short title (3-5 words, in Spanish) for a conversation that starts with: "${messageContent.slice(0, 200)}"`
    })

    const title = text.trim()
    if (title && title !== 'Nuevo Chat') {
      await updateChatTitle(chatId, title)
      console.log('[API/chat] Generated title:', title)
    }
  } catch (error) {
    console.error('[API/chat] Title generation error:', error)
  }
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
  const lastMessage = messages[messages.length - 1]
  if (lastMessage?.role === 'user') {
    const textContent = extractTextContent(lastMessage)

    await addMessage({
      chatId,
      role: 'user',
      content: textContent,
      parts: lastMessage.parts
    })

    // Generate title for new chats (fire and forget)
    if (!chat.title || chat.title === 'Nuevo Chat') {
      generateTitle(chatId, textContent).catch(console.error)
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
