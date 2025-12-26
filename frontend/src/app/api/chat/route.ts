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

// Parse OpenAI SSE stream and convert to AI SDK format
async function* convertOpenAIStreamToAISDK(reader: ReadableStreamDefaultReader<Uint8Array>) {
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim();
        if (data === '[DONE]') continue;

        try {
          const parsed = JSON.parse(data);
          const delta = parsed.choices?.[0]?.delta;

          if (delta?.content) {
            // AI SDK format: type 0 is text-delta
            yield `0:${JSON.stringify(delta.content)}\n`;
          }

          // Handle tool calls if present
          if (delta?.tool_calls) {
            for (const tc of delta.tool_calls) {
              if (tc.function?.name) {
                yield `9:${JSON.stringify({
                  toolCallId: tc.id || `call_${Date.now()}`,
                  toolName: tc.function.name,
                })}\n`;
              }
              if (tc.function?.arguments) {
                yield `a:${JSON.stringify({
                  toolCallId: tc.id || `call_${Date.now()}`,
                  argsTextDelta: tc.function.arguments,
                })}\n`;
              }
            }
          }
        } catch {
          // Skip invalid JSON
        }
      }
    }
  }

  // Send finish message
  yield `d:{"finishReason":"stop"}\n`;
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

  // Convert OpenAI SSE to AI SDK format
  const reader = response.body.getReader();
  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      try {
        for await (const chunk of convertOpenAIStreamToAISDK(reader)) {
          controller.enqueue(encoder.encode(chunk));
        }
      } catch (error) {
        console.error('Stream error:', error);
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'X-Vercel-AI-Data-Stream': 'v1',
    },
  });
}
