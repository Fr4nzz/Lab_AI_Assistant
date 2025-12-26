export async function POST(req: Request) {
  const formData = await req.formData();

  // Forward to Python backend which handles native Gemini audio
  const response = await fetch(`${process.env.BACKEND_URL}/api/chat/audio`, {
    method: 'POST',
    body: formData,
  });

  return new Response(response.body, {
    headers: { 'Content-Type': 'text/event-stream' },
  });
}
