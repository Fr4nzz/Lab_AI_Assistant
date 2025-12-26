import { type NextRequest } from 'next/server';
import { createUIMessageStream, createUIMessageStreamResponse } from 'ai';

// Convert AI SDK v6 message format to OpenAI format
function convertMessages(messages: Array<{
  role: string;
  parts?: Array<{ type: string; text?: string; [key: string]: unknown }>;
  content?: string;
}>) {
  return messages.map(msg => {
    if (typeof msg.content === 'string') {
      return { role: msg.role, content: msg.content };
    }
    if (msg.parts) {
      const textContent = msg.parts
        .filter(part => part.type === 'text' && part.text)
        .map(part => part.text)
        .join('');
      return { role: msg.role, content: textContent };
    }
    return { role: msg.role, content: '' };
  });
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
  const { messages, model, enabledTools } = body;

  console.log('[API/chat] Received request with', messages?.length, 'messages');

  const openaiMessages = convertMessages(messages);

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

  // Use AI SDK's createUIMessageStream for proper format
  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      let chunkCount = 0;

      // Send text-start
      writer.write({ type: 'text-start', id: messageId });

      for await (const text of parseOpenAIStream(reader)) {
        chunkCount++;
        if (chunkCount <= 3) {
          console.log(`[API/chat] Chunk ${chunkCount}:`, text.slice(0, 50));
        }
        // Send text-delta with correct format
        writer.write({ type: 'text-delta', id: messageId, delta: text });
      }

      // Send text-end
      writer.write({ type: 'text-end', id: messageId });

      console.log('[API/chat] Stream complete, total chunks:', chunkCount);
    },
    onError: (error) => {
      console.error('[API/chat] Stream error:', error);
      return 'An error occurred';
    },
  });

  return createUIMessageStreamResponse({ stream });
}
