import { NextRequest, NextResponse } from 'next/server';
import { getChats, createChat } from '@/lib/db';

// GET /api/db/chats - List all chats
export async function GET() {
  try {
    const chats = await getChats();
    return NextResponse.json(chats);
  } catch (error) {
    console.error('Error getting chats:', error);
    return NextResponse.json({ error: 'Failed to get chats' }, { status: 500 });
  }
}

// POST /api/db/chats - Create new chat
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const chat = await createChat(body.title);
    return NextResponse.json(chat);
  } catch (error) {
    console.error('Error creating chat:', error);
    return NextResponse.json({ error: 'Failed to create chat' }, { status: 500 });
  }
}
