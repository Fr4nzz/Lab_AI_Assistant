import { generateText } from 'ai';
import { createOpenRouter } from '@openrouter/ai-sdk-provider';

const openrouter = createOpenRouter({
  apiKey: process.env.OPENROUTER_API_KEY,
});

export async function POST(req: Request) {
  const { message } = await req.json();

  console.log('[API/chat/title] Generating title for message:', message?.slice(0, 50));

  try {
    const { text } = await generateText({
      // Same FREE model as Lobechat was using
      model: openrouter('nvidia/nemotron-3-nano-30b-a3b:free'),
      prompt: `Generate a very short title (3-5 words, in Spanish) for a conversation that starts with: "${message}"`,
    });

    console.log('[API/chat/title] Generated title:', text);
    return Response.json({ title: text.trim() });
  } catch (error) {
    console.error('[API/chat/title] Failed to generate title:', error);
    // Return a fallback title
    return Response.json({ title: 'Nuevo Chat' });
  }
}
