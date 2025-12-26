import { type NextRequest } from 'next/server';
import { createUIMessageStream, createUIMessageStreamResponse } from 'ai';
import { addMessage, saveFile, createChat, getChat, updateChat, ChatAttachment, getFileUrl } from '@/lib/db';

interface MessagePart {
  type: string;
  text?: string;
  data?: string;
  mimeType?: string;
  [key: string]: unknown;
}

interface Message {
  role: string;
  parts?: MessagePart[];
  content?: string;
}

// Convert AI SDK v6 message format to OpenAI format (with multimodal support)
function convertMessages(messages: Message[]) {
  return messages.map(msg => {
    if (typeof msg.content === 'string') {
      return { role: msg.role, content: msg.content };
    }

    if (msg.parts) {
      // Check if there are any non-text parts (images, audio, etc.)
      const hasMedia = msg.parts.some(p =>
        p.type === 'file' || p.type === 'image' || p.type === 'audio'
      );

      if (hasMedia) {
        // Convert to OpenAI multimodal format
        const content: Array<{ type: string; text?: string; image_url?: { url: string }; data?: string; mime_type?: string }> = [];

        for (const part of msg.parts) {
          if (part.type === 'text' && part.text) {
            content.push({ type: 'text', text: part.text });
          } else if (part.type === 'file' || part.type === 'image') {
            // Image - use image_url format for OpenAI compatibility
            const url = (part as { url?: string }).url || '';
            if (url) {
              content.push({ type: 'image_url', image_url: { url } });
            } else if (part.data && part.mimeType) {
              // Inline data
              content.push({
                type: 'image_url',
                image_url: { url: `data:${part.mimeType};base64,${part.data}` }
              });
            }
          } else if (part.type === 'audio' && part.data && part.mimeType) {
            // Audio - use media format for Gemini
            content.push({
              type: 'media',
              data: part.data,
              mime_type: part.mimeType
            });
          }
        }

        return { role: msg.role, content };
      } else {
        // Text only - use string content
        const textContent = msg.parts
          .filter(part => part.type === 'text' && part.text)
          .map(part => part.text)
          .join('');
        return { role: msg.role, content: textContent };
      }
    }

    return { role: msg.role, content: '' };
  });
}

// Extract text content from message for storage
function getTextContent(msg: Message): string {
  if (typeof msg.content === 'string') {
    return msg.content;
  }
  if (msg.parts) {
    return msg.parts
      .filter(p => p.type === 'text' && p.text)
      .map(p => p.text)
      .join('');
  }
  return '';
}

// Parse OpenAI SSE stream
async function* parseOpenAIStream(reader: ReadableStreamDefaultReader<Uint8Array>) {
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmedLine = line.trim();
      if (trimmedLine.startsWith('data: ')) {
        const data = trimmedLine.slice(6).trim();
        if (data === '[DONE]') {
          return;
        }
        try {
          const parsed = JSON.parse(data);
          const delta = parsed.choices?.[0]?.delta;
          if (delta?.content) {
            yield delta.content;
          }
        } catch {
          // Skip invalid JSON
        }
      }
    }
  }
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { messages, model, enabledTools, chatId: providedChatId } = body;

  console.log('[API/chat] Received request with', messages?.length, 'messages');

  // Get or create chat for storage
  let chatId = providedChatId;
  if (!chatId) {
    const chat = await createChat('New Chat');
    chatId = chat.id;
  }

  // Get the last user message for storage
  const lastUserMessage = messages[messages.length - 1];

  // Store user message (if it's a user message)
  if (lastUserMessage?.role === 'user') {
    const textContent = getTextContent(lastUserMessage);

    // Check for file attachments in parts
    const attachments: ChatAttachment[] = [];
    if (lastUserMessage.parts) {
      for (const part of lastUserMessage.parts) {
        if ((part.type === 'file' || part.type === 'image' || part.type === 'audio') && part.data && part.mimeType) {
          // Save file from base64 data
          const buffer = Buffer.from(part.data as string, 'base64');
          const filename = (part as { name?: string }).name || `file_${Date.now()}`;
          const attachment = await saveFile(buffer, filename, part.mimeType);
          attachments.push(attachment);
        }
      }
    }

    await addMessage(
      chatId,
      'user',
      textContent,
      lastUserMessage,  // Store raw for debugging
      attachments
    );
  }

  // Convert messages for backend
  const openaiMessages = convertMessages(messages);

  console.log('[API/chat] Converted messages:', JSON.stringify(openaiMessages.slice(-1), null, 2).slice(0, 500));

  const backendResponse = await fetch(`${process.env.BACKEND_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: model || 'lab-assistant',
      messages: openaiMessages,
      stream: true,
      tools: enabledTools,
    }),
  });

  console.log('[API/chat] Backend response status:', backendResponse.status);

  if (!backendResponse.ok || !backendResponse.body) {
    return new Response(JSON.stringify({ error: 'Backend error' }), {
      status: backendResponse.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const reader = backendResponse.body.getReader();
  const messageId = `msg_${Date.now()}`;

  // Collect full response for storage
  let fullResponse = '';

  // Use AI SDK's createUIMessageStream for proper format
  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      let chunkCount = 0;

      // Send text-start
      writer.write({ type: 'text-start', id: messageId });

      for await (const text of parseOpenAIStream(reader)) {
        chunkCount++;
        fullResponse += text;

        if (chunkCount <= 3) {
          console.log(`[API/chat] Chunk ${chunkCount}:`, text.slice(0, 50));
        }
        // Send text-delta with correct format
        writer.write({ type: 'text-delta', id: messageId, delta: text });
      }

      // Send text-end
      writer.write({ type: 'text-end', id: messageId });

      console.log('[API/chat] Stream complete, total chunks:', chunkCount);

      // Store assistant response in database
      if (fullResponse) {
        await addMessage(chatId, 'assistant', fullResponse);
      }
    },
    onError: (error) => {
      console.error('[API/chat] Stream error:', error);
      return 'An error occurred';
    },
  });

  return createUIMessageStreamResponse({
    stream,
    headers: {
      'X-Chat-Id': chatId,
    },
  });
}
