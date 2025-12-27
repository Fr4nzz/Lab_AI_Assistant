// Retry fetch with exponential backoff
async function fetchWithRetry(
  url: string,
  maxRetries = 3,
  initialDelayMs = 500
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await fetch(url);
      return response;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Check if it's a connection error (backend not ready)
      const isConnectionError = lastError.message.includes('ECONNREFUSED') ||
                                 lastError.message.includes('fetch failed') ||
                                 lastError.message.includes('ENOTFOUND');

      if (!isConnectionError || attempt >= maxRetries - 1) {
        throw lastError;
      }

      // Exponential backoff: 500ms, 1s, 2s
      const delayMs = initialDelayMs * Math.pow(2, attempt);
      console.log(`[API/browser/tabs/detailed] Backend not ready, retrying in ${delayMs}ms (attempt ${attempt + 1}/${maxRetries})`);
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }
  }

  throw lastError || new Error('Max retries exceeded');
}

export async function GET() {
  try {
    const response = await fetchWithRetry(`${process.env.BACKEND_URL}/api/browser/tabs/detailed`);
    const data = await response.json();
    return Response.json(data);
  } catch (error) {
    console.error('Failed to fetch detailed browser tabs:', error);
    return Response.json({ tabs: [], error: 'Failed to fetch tabs - backend may be starting up' });
  }
}
