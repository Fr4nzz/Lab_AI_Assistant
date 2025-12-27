import { NextRequest, NextResponse } from 'next/server';
import { getMessages, addMessage, saveFile, ChatAttachment } from '@/lib/db';

// GET /api/db/chats/[chatId]/messages - Get all messages for a chat
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ chatId: string }> }
) {
  try {
    const { chatId } = await params;
    const messages = await getMessages(chatId);
    return NextResponse.json(messages);
  } catch (error) {
    console.error('Error getting messages:', error);
    return NextResponse.json({ error: 'Failed to get messages' }, { status: 500 });
  }
}

// POST /api/db/chats/[chatId]/messages - Add a message to a chat
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ chatId: string }> }
) {
  try {
    const { chatId } = await params;

    // Check if it's FormData (with files) or JSON
    const contentType = request.headers.get('content-type') || '';

    let role: 'user' | 'assistant';
    let content: string;
    let rawContent: unknown;
    let attachments: ChatAttachment[] = [];
    let metadata: { model?: string; tokens?: number; duration?: number } | undefined;

    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();

      role = formData.get('role') as 'user' | 'assistant';
      content = formData.get('content') as string || '';
      rawContent = formData.get('rawContent')
        ? JSON.parse(formData.get('rawContent') as string)
        : undefined;

      // Process files
      const files = formData.getAll('files') as File[];
      for (const file of files) {
        const buffer = Buffer.from(await file.arrayBuffer());
        const attachment = await saveFile(buffer, file.name, file.type);
        attachments.push(attachment);
      }

      if (formData.get('metadata')) {
        metadata = JSON.parse(formData.get('metadata') as string);
      }
    } else {
      const body = await request.json();
      role = body.role;
      content = body.content;
      rawContent = body.rawContent;
      attachments = body.attachments || [];
      metadata = body.metadata;
    }

    const message = await addMessage(chatId, role, content, rawContent, attachments, metadata);
    return NextResponse.json(message);
  } catch (error) {
    console.error('Error adding message:', error);
    return NextResponse.json({ error: 'Failed to add message' }, { status: 500 });
  }
}
