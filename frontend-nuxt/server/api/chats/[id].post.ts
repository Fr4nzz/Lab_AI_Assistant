import { z } from 'zod'
import { randomUUID } from 'crypto'
import { getChat, addMessage, updateChatTitle } from '../../utils/db'
import { generateText } from 'ai'
import { createOpenRouter } from '@openrouter/ai-sdk-provider'
import { getBestTitleModel } from '../../utils/openrouter-models'
import { NuxtStreamAdapter, createStreamHeaders } from '../../utils/streamAdapter'
import {
  extractImageParts,
  processImagesForRotation,
  replaceImageParts,
  type ImagePart
} from '../../utils/imageRotation'

defineRouteMeta({
  openAPI: {
    description: 'Send message to AI and stream response.',
    tags: ['chat']
  }
})

// Generate title for a chat using best practices for prompt engineering
async function generateTitle(chatId: string, messageContent: string): Promise<void> {
  const config = useRuntimeConfig()

  if (!config.openrouterApiKey) {
    console.log('[API/chat] No OpenRouter key configured in OPENROUTER_API_KEY env var, skipping title generation')
    console.log('[API/chat] Add your key to frontend-nuxt/.env file')
    return
  }

  try {
    // Get best available free model for title generation
    const modelId = await getBestTitleModel()
    console.log('[API/chat] Generating title with:', modelId)

    const openrouter = createOpenRouter({
      apiKey: config.openrouterApiKey
    })

    // Improved prompt with:
    // - Clear role assignment
    // - Specific format constraints
    // - Few-shot examples
    // - Explicit prohibition of markdown/formatting
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

    const { text } = await generateText({
      model: openrouter(modelId),
      prompt,
      temperature: 0.3,
      maxTokens: 20
    })

    // Clean up the title - remove any markdown or unwanted formatting
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

    if (title && title !== 'Nuevo Chat' && title.length > 0) {
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
          if (part.mediaType?.startsWith('audio/') || part.mediaType?.startsWith('video/')) {
            return { type: 'media', data: part.data, mime_type: part.mediaType }
          }
          if (part.url) {
            return { type: 'image_url', image_url: { url: part.url } }
          }
          if (part.data && part.mediaType) {
            return { type: 'image_url', image_url: { url: `data:${part.mediaType};base64,${part.data}` } }
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

// Create stream that handles image rotation before proxying to backend
async function createRotationAwareStream(
  config: ReturnType<typeof useRuntimeConfig>,
  chatId: string,
  messages: any[],
  imageParts: ImagePart[],
  model: string | undefined,
  enabledTools: string[] | undefined,
  showStats: boolean
): Promise<ReadableStream> {
  const adapter = new NuxtStreamAdapter()
  const encoder = new TextEncoder()
  const backendUrl = config.backendUrl || 'http://localhost:8000'

  return new ReadableStream({
    async start(controller) {
      let fullResponse = ''

      try {
        // 1. Start the message
        controller.enqueue(encoder.encode(adapter.startMessage()))

        // 2. Emit image-rotation tool start
        const toolCallId = `call_rotation_${randomUUID().slice(0, 8)}`
        controller.enqueue(encoder.encode(adapter.toolStart(toolCallId, 'image-rotation')))
        controller.enqueue(encoder.encode(adapter.toolInputAvailable(toolCallId, 'image-rotation', {
          images: imageParts.map(p => p.name || 'image'),
          count: imageParts.length
        })))

        // 3. Process images for rotation
        console.log(`[API/chat] Processing ${imageParts.length} images for rotation`)
        const { results, processedImages } = await processImagesForRotation(imageParts)

        // Count how many were actually rotated
        const rotatedCount = results.filter(r => r.applied).length
        const detectedCount = results.filter(r => r.originalRotation !== 0).length

        // 4. Emit tool output with results
        controller.enqueue(encoder.encode(adapter.toolOutputAvailable(toolCallId, {
          processed: results.length,
          rotated: rotatedCount,
          detected: detectedCount,
          results: results.map(r => ({
            name: r.name,
            rotation: r.originalRotation,
            applied: r.applied
          }))
        })))

        // 5. Emit file parts for rotated images (thumbnails in chat)
        for (let i = 0; i < results.length; i++) {
          const result = results[i]
          if (result && result.originalRotation !== 0) {
            const processedImage = processedImages[i]
            if (processedImage && processedImage.url) {
              controller.enqueue(encoder.encode(adapter.filePart(
                processedImage.url,
                processedImage.mediaType
              )))
            }
          }
        }

        // 6. Replace images in the last message with processed versions
        const lastMessage = messages[messages.length - 1]
        if (lastMessage?.parts) {
          lastMessage.parts = replaceImageParts(lastMessage.parts, processedImages)
        }

        // 7. Convert and forward to backend
        const backendMessages = convertMessagesForBackend(messages)

        console.log(`[API/chat] Proxying to backend with ${rotatedCount} rotated images`)

        const response = await fetch(`${backendUrl}/api/chat/aisdk`, {
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

        if (!response.ok || !response.body) {
          controller.enqueue(encoder.encode(adapter.error('Backend not available')))
          controller.enqueue(encoder.encode(adapter.finish('error')))
          controller.close()
          return
        }

        // 8. Pipe backend stream, filtering out its "start" event (we already sent one)
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let skipStart = true

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const text = decoder.decode(value, { stream: true })

          // Filter out the backend's "start" event since we already sent one
          if (skipStart) {
            const lines = text.split('\n')
            const filteredLines = lines.filter(line => {
              if (line.startsWith('data: ')) {
                try {
                  const parsed = JSON.parse(line.slice(6))
                  if (parsed.type === 'start') {
                    skipStart = false
                    return false // Skip this line
                  }
                } catch {
                  // Not JSON, keep it
                }
              }
              return true
            })
            const filteredText = filteredLines.join('\n')
            if (filteredText.trim()) {
              controller.enqueue(encoder.encode(filteredText))
            }
          } else {
            controller.enqueue(value)
          }

          // Collect text for database storage
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
        controller.enqueue(encoder.encode(adapter.error(String(error))))
        controller.enqueue(encoder.encode(adapter.finish('error')))
        controller.close()
      }
    }
  })
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  await getUserSession(event)

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

  // Check for images in the last user message
  const imageParts = lastMessage?.parts ? extractImageParts(lastMessage.parts) : []

  // If we have images, use rotation-aware streaming
  if (imageParts.length > 0) {
    console.log(`[API/chat] Found ${imageParts.length} images, processing rotation`)

    const stream = await createRotationAwareStream(
      config,
      chatId,
      messages,
      imageParts,
      model,
      enabledTools,
      showStats
    )

    return new Response(stream, {
      headers: createStreamHeaders(chatId)
    })
  }

  // No images - proceed with standard backend proxy
  const backendUrl = config.backendUrl || 'http://localhost:8000'
  const backendMessages = convertMessagesForBackend(messages)

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
    headers: createStreamHeaders(chatId)
  })
})
