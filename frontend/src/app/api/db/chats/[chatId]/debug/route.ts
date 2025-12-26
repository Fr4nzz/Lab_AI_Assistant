import { NextRequest, NextResponse } from 'next/server';
import { getAllMessagesForDebug } from '@/lib/db';

// GET /api/db/chats/[chatId]/debug - Get full debug info for a chat
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ chatId: string }> }
) {
  try {
    const { chatId } = await params;
    const debugInfo = await getAllMessagesForDebug(chatId);
    return NextResponse.json(debugInfo);
  } catch (error) {
    console.error('Error getting debug info:', error);
    return NextResponse.json({ error: 'Failed to get debug info' }, { status: 500 });
  }
}
