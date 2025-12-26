export async function POST(req: Request) {
  const { tool, args } = await req.json();

  try {
    const response = await fetch(`${process.env.BACKEND_URL}/api/tools/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool, args }),
    });

    const data = await response.json();
    return Response.json(data);
  } catch (error) {
    console.error('Failed to execute tool:', error);
    return Response.json({ error: 'Failed to execute tool' }, { status: 500 });
  }
}
