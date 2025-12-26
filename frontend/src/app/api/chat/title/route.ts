import { generateText } from 'ai';
import { createOpenRouter } from '@openrouter/ai-sdk-provider';

const openrouter = createOpenRouter({
  apiKey: process.env.OPENROUTER_API_KEY,
});

export async function POST(req: Request) {
  const { message } = await req.json();

  try {
    const { text } = await generateText({
      // Same FREE model as Lobechat was using
      model: openrouter('nvidia/nemotron-3-nano-30b-a3b:free'),
      prompt: `Generate a very short title (3-5 words, in Spanish) for a conversation that starts with: "${message}"`,
    });

    return Response.json({ title: text.trim() });
  } catch (error) {
    console.error('Failed to generate title:', error);
    // Return a fallback title
    return Response.json({ title: 'Nuevo Chat' });
  }
}
