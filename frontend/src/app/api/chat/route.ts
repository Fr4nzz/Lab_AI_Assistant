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

  const openaiMessages = convertMessages(messages);

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

  if (!response.ok || !response.body) {
    return new Response(JSON.stringify({ error: 'Backend error' }), {
      status: response.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Create a TransformStream to convert OpenAI SSE to AI SDK format
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  let buffer = '';

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
            controller.enqueue(encoder.encode(`d:{"finishReason":"stop"}\n`));
            continue;
          }

          try {
            const parsed = JSON.parse(data);
            const delta = parsed.choices?.[0]?.delta;

            if (delta?.content) {
              // AI SDK format: type 0 is text-delta
              controller.enqueue(encoder.encode(`0:${JSON.stringify(delta.content)}\n`));
            }

            // Check for finish_reason
            if (parsed.choices?.[0]?.finish_reason === 'stop') {
              controller.enqueue(encoder.encode(`d:{"finishReason":"stop"}\n`));
            }
          } catch {
            // Skip invalid JSON
          }
        }
      }
    },
    flush(controller) {
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
