import { type NextRequest } from 'next/server';

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

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { messages, model, enabledTools } = body;

  console.log('[API/chat] Received request with', messages?.length, 'messages');

  const openaiMessages = convertMessages(messages);
  console.log('[API/chat] Converted messages:', JSON.stringify(openaiMessages).slice(0, 200));

  const response = await fetch(`${process.env.BACKEND_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: model || 'lab-assistant',
      messages: openaiMessages,
      stream: true,
      tools: enabledTools,
    }),
  });

  console.log('[API/chat] Backend response status:', response.status);

  if (!response.ok || !response.body) {
    console.error('[API/chat] Backend error:', response.status);
    return new Response(JSON.stringify({ error: 'Backend error' }), {
      status: response.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Create a TransformStream to convert OpenAI SSE to AI SDK format
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  let buffer = '';
  let chunkCount = 0;

  const transformStream = new TransformStream({
    transform(chunk, controller) {
      buffer += decoder.decode(chunk, { stream: true });

      // Process complete lines
      const lines = buffer.split('\n');
      // Keep the last incomplete line in buffer
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine.startsWith('data: ')) {
          const data = trimmedLine.slice(6).trim();

          if (data === '[DONE]') {
            console.log('[API/chat] Received [DONE], sending finish');
            controller.enqueue(encoder.encode(`d:{"finishReason":"stop"}\n`));
            continue;
          }

          try {
            const parsed = JSON.parse(data);
            const delta = parsed.choices?.[0]?.delta;

            if (delta?.content) {
              chunkCount++;
              if (chunkCount <= 3 || chunkCount % 10 === 0) {
                console.log(`[API/chat] Chunk ${chunkCount}:`, delta.content.slice(0, 50));
              }
              // AI SDK format: type 0 is text-delta
              const aiSdkChunk = `0:${JSON.stringify(delta.content)}\n`;
              controller.enqueue(encoder.encode(aiSdkChunk));
            }

            // Check for finish_reason
            if (parsed.choices?.[0]?.finish_reason === 'stop') {
              console.log('[API/chat] Received finish_reason: stop');
              controller.enqueue(encoder.encode(`d:{"finishReason":"stop"}\n`));
            }
          } catch (e) {
            // Skip invalid JSON but log it
            if (data.length > 0 && data !== '') {
              console.log('[API/chat] Failed to parse:', data.slice(0, 100));
            }
          }
        }
      }
    },
    flush(controller) {
      console.log('[API/chat] Stream flush, total chunks:', chunkCount);
      // Process any remaining data in buffer
      if (buffer.trim().startsWith('data: ')) {
        const data = buffer.trim().slice(6).trim();
        if (data === '[DONE]') {
          controller.enqueue(encoder.encode(`d:{"finishReason":"stop"}\n`));
        }
      }
    }
  });

  // Pipe the response through the transform
  const transformedStream = response.body.pipeThrough(transformStream);

  return new Response(transformedStream, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'X-Vercel-AI-Data-Stream': 'v1',
    },
  });
}
