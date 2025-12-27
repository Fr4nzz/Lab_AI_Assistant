export async function GET() {
  try {
    const response = await fetch(`${process.env.BACKEND_URL}/api/browser/tabs`);
    const data = await response.json();
    return Response.json(data);
  } catch (error) {
    console.error('Failed to fetch browser tabs:', error);
    return Response.json({ tabs: [] });
  }
}
