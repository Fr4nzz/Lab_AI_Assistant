import { z } from 'zod'
import { randomUUID } from 'crypto'
import { getChat, addMessage, updateChatTitle, getUserSettings } from '../../utils/db'
import { generateText } from 'ai'
import { createOpenRouter } from '@openrouter/ai-sdk-provider'
import { getBestTitleModel } from '../../utils/openrouter-models'
import { NuxtStreamAdapter, createStreamHeaders } from '../../utils/streamAdapter'
import {
  extractImageParts,
  type ImagePart
} from '../../utils/imageRotation'
import {
  processImagesWithPreprocessing,
  buildPreprocessingToolOutput,
  replaceWithProcessedImages
} from '../../utils/preprocessing'

defineRouteMeta({
  openAPI: {
    description: 'Send message to AI and stream response.',
    tags: ['chat']
  }
})

// Types for collecting message parts from stream
interface ToolPart {
  type: 'tool-invocation'
  toolCallId: string
  toolName: string
  state: 'partial-call' | 'call' | 'result' | 'error'
  args?: Record<string, unknown>
  result?: unknown
}

interface FilePart {
  type: 'file'
  url: string
  mediaType: string
}

interface TextPart {
  type: 'text'
  text: string
}

type MessagePart = TextPart | ToolPart | FilePart

// Collector for parsing stream events into message parts
class MessagePartsCollector {
  private textContent = ''
  private toolCalls = new Map<string, ToolPart>()
  private fileParts: FilePart[] = []

  addTextDelta(delta: string) {
    this.textContent += delta
  }

  toolInputStart(toolCallId: string, toolName: string) {
    this.toolCalls.set(toolCallId, {
      type: 'tool-invocation',
      toolCallId,
      toolName,
      state: 'partial-call'
    })
  }

  toolInputAvailable(toolCallId: string, toolName: string, input: Record<string, unknown>) {
    const existing = this.toolCalls.get(toolCallId)
    if (existing) {
      existing.state = 'call'
      existing.args = input
    } else {
      this.toolCalls.set(toolCallId, {
        type: 'tool-invocation',
        toolCallId,
        toolName,
        state: 'call',
        args: input
      })
    }
  }

  toolOutputAvailable(toolCallId: string, output: unknown) {
    const existing = this.toolCalls.get(toolCallId)
    if (existing) {
      existing.state = 'result'
      existing.result = output
    }
  }

  addFile(url: string, mediaType: string) {
    this.fileParts.push({ type: 'file', url, mediaType })
  }

  getTextContent(): string {
    return this.textContent
  }

  // Build the parts array in correct order
  buildParts(): MessagePart[] {
    const parts: MessagePart[] = []

    // Add tool parts first (they appear before text in the UI)
    for (const tool of this.toolCalls.values()) {
      parts.push(tool)
    }

    // Add file parts (rotated images shown after tools)
    for (const file of this.fileParts) {
      parts.push(file)
    }

    // Add text part last (main response)
    if (this.textContent) {
      parts.push({ type: 'text', text: this.textContent })
    }

    return parts
  }
}

// Generate title for a chat using best practices for prompt engineering
async function generateTitle(chatId: string, messageContent: string): Promise<void> {
  const config = useRuntimeConfig()

  if (!config.openrouterApiKey) {
    console.log('[API/chat] No OpenRouter key configured in OPENROUTER_API_KEY env var, skipping title generation')
    console.log('[API/chat] Add your key to frontend-nuxt/.env file')
    return
  }

  try {
    const modelId = await getBestTitleModel()
    console.log('[API/chat] Generating title with:', modelId)

    const openrouter = createOpenRouter({
      apiKey: config.openrouterApiKey
    })

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

    let title = text.trim()
      .replace(/^\*\*|\*\*$/g, '')
      .replace(/^#+\s*/, '')
      .replace(/^["']|["']$/g, '')
      .replace(/^Título:\s*/i, '')
      .replace(/\n.*/g, '')
      .trim()

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

// Parse a single SSE line and update the collector
function parseSSELine(line: string, collector: MessagePartsCollector): boolean {
  if (!line.startsWith('data: ')) return false

  const data = line.slice(6)
  if (data === '[DONE]') return false

  try {
    const parsed = JSON.parse(data)

    switch (parsed.type) {
      case 'text-delta':
        if (parsed.delta) {
          collector.addTextDelta(parsed.delta)
        }
        break

      case 'tool-input-start':
        collector.toolInputStart(parsed.toolCallId, parsed.toolName)
        break

      case 'tool-input-available':
        collector.toolInputAvailable(parsed.toolCallId, parsed.toolName, parsed.input || {})
        break

      case 'tool-output-available':
        collector.toolOutputAvailable(parsed.toolCallId, parsed.output)
        break

      case 'file':
        collector.addFile(parsed.url, parsed.mediaType)
        break
    }

    return true
  } catch {
    return false
  }
}

// Create stream that handles image preprocessing (YOLOE + rotation) before proxying to backend
async function createPreprocessingAwareStream(
  config: ReturnType<typeof useRuntimeConfig>,
  chatId: string,
  messages: any[],
  imageParts: ImagePart[],
  model: string | undefined,
  enabledTools: string[] | undefined,
  showStats: boolean,
  visitorId?: string
): Promise<ReadableStream> {
  const adapter = new NuxtStreamAdapter()
  const encoder = new TextEncoder()
  const backendUrl = config.backendUrl || 'http://localhost:8000'

  return new ReadableStream({
    async start(controller) {
      const collector = new MessagePartsCollector()
      let incompleteSSELine = ''

      try {
        // 1. Start the message
        controller.enqueue(encoder.encode(adapter.startMessage()))

        // 2. Check if images are already preprocessed (client-side preprocessing completed)
        const allPreprocessed = imageParts.every(p => p.preprocessed === true || p.rotatedBase64)
        const preprocessingToolCallId = `call_preprocessing_${randomUUID().slice(0, 8)}`

        let rotatedCount = 0
        let croppedCount = 0
        let preprocessingTime = 0

        if (allPreprocessed) {
          // Images already preprocessed on client - just emit completion status
          console.log(`[API/chat] Images already preprocessed on client, skipping server-side preprocessing`)

          controller.enqueue(encoder.encode(adapter.toolStart(preprocessingToolCallId, 'image-preprocessing')))
          const toolInput = {
            images: imageParts.map(p => p.name || 'image'),
            count: imageParts.length,
            cached: true
          }
          controller.enqueue(encoder.encode(adapter.toolInputAvailable(preprocessingToolCallId, 'image-preprocessing', toolInput)))

          collector.toolInputStart(preprocessingToolCallId, 'image-preprocessing')
          collector.toolInputAvailable(preprocessingToolCallId, 'image-preprocessing', toolInput)

          // Count from client-side preprocessing
          rotatedCount = imageParts.filter(p => (p.rotation ?? 0) !== 0).length
          croppedCount = imageParts.filter(p => p.useCrop).length

          const toolOutput = {
            processed: imageParts.length,
            rotated: rotatedCount,
            cropped: croppedCount,
            cached: true,
            results: imageParts.map((p, i) => ({
              imageIndex: i + 1,
              rotation: p.rotation ?? 0,
              useCrop: p.useCrop ?? false
            }))
          }
          controller.enqueue(encoder.encode(adapter.toolOutputAvailable(preprocessingToolCallId, toolOutput)))
          collector.toolOutputAvailable(preprocessingToolCallId, toolOutput)

        } else {
          // Run preprocessing pipeline on server
          controller.enqueue(encoder.encode(adapter.toolStart(preprocessingToolCallId, 'image-preprocessing')))
          const toolInput = {
            images: imageParts.map(p => p.name || 'image'),
            count: imageParts.length
          }
          controller.enqueue(encoder.encode(adapter.toolInputAvailable(preprocessingToolCallId, 'image-preprocessing', toolInput)))

          collector.toolInputStart(preprocessingToolCallId, 'image-preprocessing')
          collector.toolInputAvailable(preprocessingToolCallId, 'image-preprocessing', toolInput)

          console.log(`[API/chat] Processing ${imageParts.length} images through preprocessing pipeline`)

          const preprocessResult = await processImagesWithPreprocessing(
            backendUrl,
            imageParts,
            visitorId
          )

          // Emit tool output with results
          const toolOutput = buildPreprocessingToolOutput(preprocessResult, imageParts)
          controller.enqueue(encoder.encode(adapter.toolOutputAvailable(preprocessingToolCallId, toolOutput)))
          collector.toolOutputAvailable(preprocessingToolCallId, toolOutput)

          // Replace images in the last message with processed versions
          const lastMessage = messages[messages.length - 1]
          if (lastMessage?.parts) {
            lastMessage.parts = replaceWithProcessedImages(lastMessage.parts, preprocessResult.processedImages)
          }

          rotatedCount = preprocessResult.choices.filter(c => c.rotation !== 0).length
          croppedCount = preprocessResult.choices.filter(c => c.useCrop).length
          preprocessingTime = preprocessResult.timing.totalMs
        }

        // 6. Convert and forward to backend
        const backendMessages = convertMessagesForBackend(messages)

        const preprocessingStatus = allPreprocessed ? 'cached' : `${preprocessingTime}ms`
        console.log(`[API/chat] Proxying to backend with ${rotatedCount} rotated, ${croppedCount} cropped images (${preprocessingStatus} preprocessing)`)

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

        // 7. Pipe backend stream, properly handling SSE format
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let skipStartEvent = true

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const text = decoder.decode(value, { stream: true })

          // Handle partial SSE lines from previous chunk
          const fullText = incompleteSSELine + text
          const lines = fullText.split('\n')

          // Last line might be incomplete, save it for next chunk
          incompleteSSELine = lines.pop() || ''

          // Process complete lines
          const outputLines: string[] = []
          for (const line of lines) {
            // Filter out backend's start event (we already sent one)
            if (skipStartEvent && line.startsWith('data: ')) {
              try {
                const parsed = JSON.parse(line.slice(6))
                if (parsed.type === 'start') {
                  skipStartEvent = false
                  continue // Skip this line
                }
              } catch {
                // Not JSON, keep it
              }
            }

            // Parse for collector
            parseSSELine(line, collector)

            // Keep the line for output
            outputLines.push(line)
          }

          // Send to client
          if (outputLines.length > 0) {
            const output = outputLines.join('\n') + '\n'
            controller.enqueue(encoder.encode(output))
          }
        }

        // Handle any remaining incomplete line
        if (incompleteSSELine.trim()) {
          parseSSELine(incompleteSSELine, collector)
          controller.enqueue(encoder.encode(incompleteSSELine + '\n'))
        }

        controller.close()

        // Save assistant response with complete parts
        const parts = collector.buildParts()
        const textContent = collector.getTextContent()

        if (parts.length > 0 || textContent) {
          await addMessage({
            chatId,
            role: 'assistant',
            content: textContent,
            parts
          })
          console.log(`[API/chat] Saved assistant response with ${parts.length} parts, text length: ${textContent.length}`)
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
  // Verify user is authenticated (OAuth or internal API key)
  const { requireSessionOrInternal } = await import('../../utils/internalAuth')
  await requireSessionOrInternal(event)

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

  // Save user message to database BEFORE streaming (only if not already saved)
  const lastMessage = messages[messages.length - 1]
  if (lastMessage?.role === 'user') {
    const textContent = extractTextContent(lastMessage)

    // Check if this message already exists in the database (by ID or by being the last message)
    // This prevents duplicates when regenerate() is called
    const existingMessages = chat.messages || []
    const lastDbMessage = existingMessages[existingMessages.length - 1]

    // Skip saving if:
    // - Message has an ID that matches one in DB, OR
    // - Last message in DB is a user message with same content (regenerate case)
    const isAlreadySaved = lastMessage.id && existingMessages.some((m: any) => m.id === lastMessage.id)
    const isRegenerateCase = lastDbMessage?.role === 'user' && extractTextContent(lastDbMessage) === textContent

    if (!isAlreadySaved && !isRegenerateCase) {
      await addMessage({
        chatId,
        role: 'user',
        content: textContent,
        parts: lastMessage.parts
      })
      console.log('[API/chat] Saved new user message')

      // Generate title for new chats (fire and forget)
      if (!chat.title || chat.title === 'Nuevo Chat') {
        generateTitle(chatId, textContent).catch(console.error)
      }
    } else {
      console.log('[API/chat] Skipped saving duplicate user message (regenerate case)')
    }
  }

  // Check for images in the last user message
  const imageParts = lastMessage?.parts ? extractImageParts(lastMessage.parts) : []

  // If we have images, use preprocessing-aware streaming
  if (imageParts.length > 0) {
    console.log(`[API/chat] Found ${imageParts.length} images, processing with YOLOE + rotation pipeline`)

    // Get visitor ID for user settings lookup
    const visitorId = getCookie(event, 'visitor_id') || undefined

    const stream = await createPreprocessingAwareStream(
      config,
      chatId,
      messages,
      imageParts,
      model,
      enabledTools,
      showStats,
      visitorId
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
  const collector = new MessagePartsCollector()
  let incompleteSSELine = ''

  const stream = new ReadableStream({
    async start(controller) {
      const decoder = new TextDecoder()

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          controller.enqueue(value)

          // Parse stream to collect parts for storage
          const text = decoder.decode(value, { stream: true })
          const fullText = incompleteSSELine + text
          const lines = fullText.split('\n')

          // Last line might be incomplete
          incompleteSSELine = lines.pop() || ''

          for (const line of lines) {
            parseSSELine(line, collector)
          }
        }

        // Handle remaining line
        if (incompleteSSELine.trim()) {
          parseSSELine(incompleteSSELine, collector)
        }

        controller.close()

        // Save assistant response with complete parts
        const parts = collector.buildParts()
        const textContent = collector.getTextContent()

        if (parts.length > 0 || textContent) {
          await addMessage({
            chatId,
            role: 'assistant',
            content: textContent,
            parts
          })
          console.log(`[API/chat] Saved assistant response with ${parts.length} parts, text length: ${textContent.length}`)
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
