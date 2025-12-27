import { NextRequest, NextResponse } from 'next/server';
import { getChat, updateChat, deleteChat } from '@/lib/db';

interface RouteParams {
  params: Promise<{ chatId: string }>;
}

// GET /api/db/chats/[chatId] - Get single chat
export async function GET(request: NextRequest, { params }: RouteParams) {
  const { chatId } = await params;

  try {
    const chat = await getChat(chatId);
    if (!chat) {
      return NextResponse.json({ error: 'Chat not found' }, { status: 404 });
    }
    return NextResponse.json(chat);
  } catch (error) {
    console.error('Error getting chat:', error);
    return NextResponse.json({ error: 'Failed to get chat' }, { status: 500 });
  }
}

// PATCH /api/db/chats/[chatId] - Update chat (title, etc.)
export async function PATCH(request: NextRequest, { params }: RouteParams) {
  const { chatId } = await params;

  try {
    const body = await request.json();
    const updated = await updateChat(chatId, body);

    if (!updated) {
      return NextResponse.json({ error: 'Chat not found' }, { status: 404 });
    }

    return NextResponse.json(updated);
  } catch (error) {
    console.error('Error updating chat:', error);
    return NextResponse.json({ error: 'Failed to update chat' }, { status: 500 });
  }
}

// DELETE /api/db/chats/[chatId] - Delete chat and its messages
export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { chatId } = await params;

  try {
    const deleted = await deleteChat(chatId);

    if (!deleted) {
      return NextResponse.json({ error: 'Chat not found' }, { status: 404 });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error deleting chat:', error);
    return NextResponse.json({ error: 'Failed to delete chat' }, { status: 500 });
  }
}
