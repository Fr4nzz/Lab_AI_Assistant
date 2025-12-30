/**
 * Nuxt Stream Adapter for AI SDK UI Message Stream Protocol v1.
 *
 * Emits SSE events compatible with the AI SDK frontend.
 * Used for synthetic tool events (like image rotation) before proxying to backend.
 *
 * Protocol docs: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol
 */

import { randomUUID } from 'crypto'

export class NuxtStreamAdapter {
  private messageId: string
  private textId: string | null = null

  constructor(messageId?: string) {
    this.messageId = messageId || `msg_${randomUUID().slice(0, 12)}`
  }

  getMessageId(): string {
    return this.messageId
  }

  private sse(data: unknown): string {
    return `data: ${JSON.stringify(data)}\n\n`
  }

  /**
   * Start a new assistant message - REQUIRED for AI SDK to create message parts
   */
  startMessage(): string {
    return this.sse({
      type: 'start',
      messageId: this.messageId
    })
  }

  /**
   * Start a new step in the agent flow
   */
  startStep(): string {
    return this.sse({ type: 'start-step' })
  }

  /**
   * Finish the current step
   */
  finishStep(): string {
    return this.sse({ type: 'finish-step' })
  }

  /**
   * Start streaming a tool call
   */
  toolStart(toolCallId: string, toolName: string): string {
    return this.sse({
      type: 'tool-input-start',
      toolCallId,
      toolName
    })
  }

  /**
   * Signal that tool input is available (shows arguments in UI)
   */
  toolInputAvailable(toolCallId: string, toolName: string, input: Record<string, unknown>): string {
    return this.sse({
      type: 'tool-input-available',
      toolCallId,
      toolName,
      input
    })
  }

  /**
   * Signal that tool output is available (shows result in UI)
   */
  toolOutputAvailable(toolCallId: string, output: unknown): string {
    return this.sse({
      type: 'tool-output-available',
      toolCallId,
      output
    })
  }

  /**
   * Emit a complete tool execution (start + input + output)
   */
  toolComplete(
    toolName: string,
    input: Record<string, unknown>,
    output: unknown,
    toolCallId?: string
  ): string {
    const id = toolCallId || `call_${randomUUID().slice(0, 12)}`
    return (
      this.toolStart(id, toolName) +
      this.toolInputAvailable(id, toolName, input) +
      this.toolOutputAvailable(id, output)
    )
  }

  /**
   * Emit a file part (for displaying images/files in the stream)
   */
  filePart(url: string, mediaType: string, filename?: string): string {
    const data: Record<string, unknown> = {
      type: 'file',
      url,
      mediaType
    }
    if (filename) {
      data.filename = filename
    }
    return this.sse(data)
  }

  /**
   * Start a text block
   */
  textStart(): string {
    this.textId = `text_${randomUUID().slice(0, 12)}`
    return this.sse({
      type: 'text-start',
      id: this.textId
    })
  }

  /**
   * Stream a text delta
   */
  textDelta(content: string): string {
    let result = ''
    if (!this.textId) {
      result += this.textStart()
    }
    result += this.sse({
      type: 'text-delta',
      id: this.textId,
      delta: content
    })
    return result
  }

  /**
   * End a text block
   */
  textEnd(): string {
    if (!this.textId) return ''
    const result = this.sse({
      type: 'text-end',
      id: this.textId
    })
    this.textId = null
    return result
  }

  /**
   * Emit an error
   */
  error(message: string): string {
    return this.sse({
      type: 'error',
      errorText: message
    })
  }

  /**
   * Finish the message stream
   */
  finish(reason: string = 'stop'): string {
    let result = ''
    if (this.textId) {
      result += this.textEnd()
    }
    result += this.sse({ type: 'finish', finishReason: reason })
    result += 'data: [DONE]\n\n'
    return result
  }
}

/**
 * Creates SSE response headers for AI SDK streaming
 */
export function createStreamHeaders(chatId?: string): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'text/event-stream',
    'x-vercel-ai-ui-message-stream': 'v1',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive'
  }
  if (chatId) {
    headers['X-Chat-Id'] = chatId
  }
  return headers
}
