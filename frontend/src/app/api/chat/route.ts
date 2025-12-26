import { type NextRequest } from 'next/server';

// Convert AI SDK v6 message format to OpenAI format
function convertMessages(messages: Array<{
  role: string;
  parts?: Array<{ type: string; text?: string; [key: string]: unknown }>;
  content?: string;
}>) {
  return messages.map(msg => {
    // If already has content string, use it
    if (typeof msg.content === 'string') {
      return { role: msg.role, content: msg.content };
    }

    // Convert parts to content string
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

  // Convert messages to OpenAI format
  const openaiMessages = convertMessages(messages);

  // Forward to Python backend
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

  // Stream response back to client
  return new Response(response.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
