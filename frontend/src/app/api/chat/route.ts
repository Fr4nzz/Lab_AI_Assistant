import { type NextRequest } from 'next/server';
import { createUIMessageStream, createUIMessageStreamResponse, generateText } from 'ai';
import { createOpenRouter } from '@openrouter/ai-sdk-provider';
import { addMessage, saveFile, createChat, ChatAttachment, saveDebugRequest, updateDebugRequest, updateChatTitle } from '@/lib/db';

const openrouter = createOpenRouter({
  apiKey: process.env.OPENROUTER_API_KEY,
});

// Generate and save title for a chat
async function generateTitle(chatId: string, messageContent: string): Promise<void> {
  console.log('[API/chat] Generating title for chat:', chatId, 'message:', messageContent.slice(0, 50));

  try {
    const { text } = await generateText({
      model: openrouter('nvidia/nemotron-3-nano-30b-a3b:free'),
      prompt: `Generate a very short title (3-5 words, in Spanish) for a conversation that starts with: "${messageContent}"`,
    });

    const title = text.trim();
    console.log('[API/chat] Generated title:', title);

    if (title && title !== 'Nuevo Chat') {
      await updateChatTitle(chatId, title);
      console.log('[API/chat] Title saved to database');
    }
  } catch (error) {
    console.error('[API/chat] Title generation error:', error);
  }
}

// Summarize media content for debug (avoid storing huge base64 strings)
function summarizeForDebug(obj: unknown): unknown {
  if (typeof obj !== 'object' || obj === null) return obj;

  if (Array.isArray(obj)) {
    return obj.map(summarizeForDebug);
  }

  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (key === 'data' && typeof value === 'string' && value.length > 200) {
      result[key] = `[BASE64 DATA: ${value.length} chars]`;
    } else if (key === 'url' && typeof value === 'string' && value.startsWith('data:') && value.length > 200) {
      const mimeMatch = value.match(/^data:([^;]+)/);
      result[key] = `[DATA URL: ${mimeMatch?.[1] || 'unknown'}, ${value.length} chars]`;
    } else if (typeof value === 'object') {
      result[key] = summarizeForDebug(value);
    } else {
      result[key] = value;
    }
  }
  return result;
}

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
          } else if (part.type === 'file' || part.type === 'image' || part.type === 'audio') {
            const mimeType = part.mimeType || (part as { mediaType?: string }).mediaType || '';
            const url = (part as { url?: string }).url || '';
            const data = part.data || '';

            // Check if it's audio/video - use media format for Gemini native support
            if (mimeType.startsWith('audio/') || mimeType.startsWith('video/')) {
              if (data) {
                content.push({
                  type: 'media',
                  data: data,
                  mime_type: mimeType
                });
              } else if (url && url.startsWith('data:')) {
                // Extract base64 from data URL
                const base64Match = url.match(/^data:[^;]+;base64,(.+)$/);
                if (base64Match) {
                  content.push({
                    type: 'media',
                    data: base64Match[1],
                    mime_type: mimeType
                  });
                }
              }
            } else {
              // Image or other file - use image_url format
              if (url) {
                content.push({ type: 'image_url', image_url: { url } });
              } else if (data && mimeType) {
                content.push({
                  type: 'image_url',
                  image_url: { url: `data:${mimeType};base64,${data}` }
                });
              }
            }
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

// Retry fetch with exponential backoff
async function fetchWithRetry(
  url: string,
  options: RequestInit,
  maxRetries = 5,
  initialDelayMs = 1000
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);
      return response;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Check if it's a connection error (backend not ready)
      const isConnectionError = lastError.message.includes('ECONNREFUSED') ||
                                 lastError.message.includes('fetch failed') ||
                                 lastError.message.includes('ENOTFOUND');

      if (!isConnectionError || attempt >= maxRetries - 1) {
        throw lastError;
      }

      // Exponential backoff: 1s, 2s, 4s, 8s, 16s
      const delayMs = initialDelayMs * Math.pow(2, attempt);
      console.log(`[API/chat] Backend not ready, retrying in ${delayMs}ms (attempt ${attempt + 1}/${maxRetries})`);
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }
  }

  throw lastError || new Error('Max retries exceeded');
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

  console.log('[API/chat] Received request with', messages?.length, 'messages, providedChatId:', providedChatId);

  // Get or create chat for storage
  let chatId = providedChatId;
  let isNewChat = false;
  if (!chatId) {
    const chat = await createChat('Nuevo Chat');
    chatId = chat.id;
    isNewChat = true;
    console.log('[API/chat] Created new chat:', chatId);

    // Generate title for new chat in the background
    const lastUserMessage = messages[messages.length - 1];
    const messageContent = getTextContent(lastUserMessage);
    if (messageContent) {
      // Fire and forget - don't wait for title generation
      generateTitle(chatId, messageContent).catch(err =>
        console.error('[API/chat] Title generation failed:', err)
      );
    }
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
      summarizeForDebug(lastUserMessage),  // Summarize to avoid huge base64 in logs
      attachments
    );
  }

  // Convert messages for backend
  const openaiMessages = convertMessages(messages);

  // Build the backend request
  const backendRequest = {
    model: model || 'lab-assistant',
    messages: openaiMessages,
    stream: true,
    tools: enabledTools,
  };

  // Save debug info (summarized to avoid huge base64 data)
  const debugId = await saveDebugRequest(
    chatId,
    summarizeForDebug(messages),
    summarizeForDebug(backendRequest)
  );

  console.log('[API/chat] Messages count:', messages.length);
  console.log('[API/chat] Backend request (summarized):', JSON.stringify(summarizeForDebug(openaiMessages.slice(-1)), null, 2));

  let backendResponse: Response;
  try {
    // Use retry mechanism in case backend is still starting up
    backendResponse = await fetchWithRetry(
      `${process.env.BACKEND_URL}/v1/chat/completions`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(backendRequest),
      },
      5,  // max retries
      1000  // initial delay 1s
    );
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('[API/chat] Backend connection failed after retries:', errorMessage);
    await updateDebugRequest(chatId, debugId, { error: `Backend connection failed: ${errorMessage}` });
    return new Response(JSON.stringify({ error: 'Backend not available. Please wait and try again.' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  console.log('[API/chat] Backend response status:', backendResponse.status);

  if (!backendResponse.ok || !backendResponse.body) {
    await updateDebugRequest(chatId, debugId, { error: `Backend error: ${backendResponse.status}` });
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
        await updateDebugRequest(chatId, debugId, { backendResponse: fullResponse });
      }
    },
    onError: (error) => {
      console.error('[API/chat] Stream error:', error);
      updateDebugRequest(chatId, debugId, { error: String(error) });
      return 'An error occurred';
    },
  });

  console.log('[API/chat] Returning response with X-Chat-Id:', chatId, 'isNewChat:', isNewChat);

  return createUIMessageStreamResponse({
    stream,
    headers: {
      'X-Chat-Id': chatId,
      'Access-Control-Expose-Headers': 'X-Chat-Id',  // Ensure browser can read this header
    },
  });
}
