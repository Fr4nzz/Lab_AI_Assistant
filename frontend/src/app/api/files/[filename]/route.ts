import { NextRequest, NextResponse } from 'next/server';
import { getFile } from '@/lib/db';

// MIME type lookup
const MIME_TYPES: Record<string, string> = {
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.webm': 'audio/webm',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.ogg': 'audio/ogg',
  '.mp4': 'video/mp4',
  '.pdf': 'application/pdf',
};

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ filename: string }> }
) {
  const { filename } = await params;

  const file = await getFile(filename);

  if (!file) {
    return NextResponse.json({ error: 'File not found' }, { status: 404 });
  }

  // Get MIME type from extension
  const ext = filename.substring(filename.lastIndexOf('.'));
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  return new NextResponse(new Uint8Array(file), {
    headers: {
      'Content-Type': contentType,
      'Content-Length': file.length.toString(),
      'Cache-Control': 'public, max-age=31536000, immutable',
    },
  });
}
