import { z } from 'zod'
import { createChat, addMessage, updateChatTitle } from '../utils/db'
import { requireSessionOrInternal } from '../utils/internalAuth'
import { generateText } from 'ai'
import { createOpenRouter } from '@openrouter/ai-sdk-provider'
import { getBestTitleModel } from '../utils/openrouter-models'

// Generate title for a chat
async function generateTitle(chatId: string, messageContent: string): Promise<void> {
  const config = useRuntimeConfig()

  if (!config.openrouterApiKey) {
    console.log('[API/chats] No OpenRouter key, skipping title generation')
    return
  }

  try {
    const modelId = await getBestTitleModel()
    console.log('[API/chats] Generating title with:', modelId)

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
      console.log('[API/chats] Generated title:', title)
    }
  } catch (error) {
    console.error('[API/chats] Title generation error:', error)
  }
}

export default defineEventHandler(async (event) => {
  // Verify user is authenticated (OAuth or internal API key)
  await requireSessionOrInternal(event)

  const body = await readValidatedBody(event, z.object({
    id: z.string().optional(),
    title: z.string().optional(),
    message: z.object({
      role: z.string(),
      parts: z.array(z.any()).optional(),
      content: z.string().optional()
    }).optional()
  }).parse)

  // Create shared chat (no user association - visible to all users)
  const chat = await createChat({
    id: body.id,
    title: body.title || 'Nuevo Chat'
  })

  // Add initial message if provided
  if (body.message) {
    const textContent = body.message.content ||
      body.message.parts?.filter((p: any) => p.type === 'text').map((p: any) => p.text).join('') || ''

    await addMessage({
      chatId: chat.id,
      role: body.message.role as 'user' | 'assistant' | 'system',
      content: textContent,
      parts: body.message.parts
    })

    // Generate title for new chats with user messages (fire and forget)
    if (body.message.role === 'user' && textContent) {
      generateTitle(chat.id, textContent).catch(console.error)
    }
  }

  return chat
})
