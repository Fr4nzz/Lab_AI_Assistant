/**
 * Database operations for Lab Assistant AI
 *
 * Uses Drizzle ORM with SQLite for local development.
 * Maintains backward compatibility with existing API.
 */

import { promises as fs } from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';
import { eq, desc, asc } from 'drizzle-orm';
import { db, chats, messages, files } from './drizzle';

// Data directory for file storage
const DATA_DIR = path.join(process.cwd(), 'data');
const FILES_DIR = path.join(DATA_DIR, 'files');

// Generate timestamped ID: YYYYMMDD_HHMMSS_randomchars
function generateId(prefix?: string): string {
  const now = new Date();
  const timestamp = now.toISOString()
    .replace(/[-:T]/g, '')
    .replace(/\.\d{3}Z$/, '');
  const random = randomUUID().slice(0, 8);
  return prefix ? `${prefix}_${timestamp}_${random}` : `${timestamp}_${random}`;
}

// Ensure files directory exists
async function ensureFilesDirectory() {
  await fs.mkdir(FILES_DIR, { recursive: true });
}

// ============================================================
// TYPES (Backward compatible)
// ============================================================

export interface ChatAttachment {
  id: string;
  filename: string;
  mimeType: string;
  size: number;
  path: string;
  createdAt: string;
}

export interface ChatMessage {
  id: string;
  chatId: string;
  role: 'user' | 'assistant';
  content: string;
  rawContent?: unknown;
  attachments: ChatAttachment[];
  createdAt: string;
  metadata?: {
    model?: string;
    tokens?: number;
    duration?: number;
  };
}

export interface Chat {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
  userId?: string;
}

// ============================================================
// CHATS
// ============================================================

export async function getChats(userId?: string): Promise<Chat[]> {
  const query = userId
    ? db.select().from(chats).where(eq(chats.userId, userId)).orderBy(desc(chats.createdAt))
    : db.select().from(chats).orderBy(desc(chats.createdAt));

  const results = await query;

  // Get message counts for each chat
  const chatList = await Promise.all(
    results.map(async (chat) => {
      const msgs = await db.select().from(messages).where(eq(messages.chatId, chat.id));
      return {
        id: chat.id,
        title: chat.title,
        createdAt: chat.createdAt,
        updatedAt: chat.updatedAt,
        messageCount: msgs.length,
        userId: chat.userId || undefined,
      };
    })
  );

  return chatList;
}

export async function getChat(id: string): Promise<Chat | null> {
  const result = await db.select().from(chats).where(eq(chats.id, id)).limit(1);

  if (result.length === 0) return null;

  const chat = result[0];
  const msgs = await db.select().from(messages).where(eq(messages.chatId, id));

  return {
    id: chat.id,
    title: chat.title,
    createdAt: chat.createdAt,
    updatedAt: chat.updatedAt,
    messageCount: msgs.length,
    userId: chat.userId || undefined,
  };
}

export async function createChat(title: string = 'Nuevo Chat', userId?: string): Promise<Chat> {
  const id = generateId('chat');
  const now = new Date().toISOString();

  await db.insert(chats).values({
    id,
    title,
    userId: userId || null,
    createdAt: now,
    updatedAt: now,
  });

  return {
    id,
    title,
    createdAt: now,
    updatedAt: now,
    messageCount: 0,
    userId,
  };
}

export async function updateChat(id: string, updates: Partial<Chat>): Promise<Chat | null> {
  const now = new Date().toISOString();

  await db
    .update(chats)
    .set({
      ...(updates.title !== undefined && { title: updates.title }),
      ...(updates.userId !== undefined && { userId: updates.userId }),
      updatedAt: now,
    })
    .where(eq(chats.id, id));

  return getChat(id);
}

export async function updateChatTitle(id: string, title: string): Promise<Chat | null> {
  return updateChat(id, { title });
}

export async function deleteChat(id: string): Promise<boolean> {
  const result = await db.delete(chats).where(eq(chats.id, id));
  return (result.changes ?? 0) > 0;
}

// ============================================================
// MESSAGES
// ============================================================

export async function getMessages(chatId: string): Promise<ChatMessage[]> {
  const results = await db
    .select()
    .from(messages)
    .where(eq(messages.chatId, chatId))
    .orderBy(asc(messages.orderIndex), asc(messages.createdAt));

  // Get attachments for each message
  const messageList = await Promise.all(
    results.map(async (msg) => {
      const attachments = await db.select().from(files).where(eq(files.messageId, msg.id));

      return {
        id: msg.id,
        chatId: msg.chatId,
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
        rawContent: msg.rawContent,
        attachments: attachments.map((f) => ({
          id: f.id,
          filename: f.filename,
          mimeType: f.mimeType,
          size: f.size,
          path: f.path,
          createdAt: f.createdAt,
        })),
        createdAt: msg.createdAt,
        metadata: msg.metadata as ChatMessage['metadata'],
      };
    })
  );

  return messageList;
}

export async function getMessage(chatId: string, messageId: string): Promise<ChatMessage | null> {
  const msgs = await getMessages(chatId);
  return msgs.find((m) => m.id === messageId) || null;
}

export async function addMessage(
  chatId: string,
  role: 'user' | 'assistant',
  content: string,
  rawContent?: unknown,
  attachments: ChatAttachment[] = [],
  metadata?: ChatMessage['metadata']
): Promise<ChatMessage> {
  const id = generateId('msg');
  const now = new Date().toISOString();

  // Get current message count for order index
  const existingMessages = await db
    .select()
    .from(messages)
    .where(eq(messages.chatId, chatId));
  const orderIndex = existingMessages.length;

  // Insert message
  await db.insert(messages).values({
    id,
    chatId,
    role,
    content,
    rawContent: rawContent ? JSON.stringify(rawContent) : null,
    orderIndex,
    metadata: metadata ? JSON.stringify(metadata) : null,
    createdAt: now,
  });

  // Insert attachments
  for (const attachment of attachments) {
    await db.insert(files).values({
      id: attachment.id,
      messageId: id,
      filename: attachment.filename,
      mimeType: attachment.mimeType,
      path: attachment.path,
      size: attachment.size,
      createdAt: attachment.createdAt,
    });
  }

  // Update chat's updatedAt
  await db.update(chats).set({ updatedAt: now }).where(eq(chats.id, chatId));

  return {
    id,
    chatId,
    role,
    content,
    rawContent,
    attachments,
    createdAt: now,
    metadata,
  };
}

// ============================================================
// FILES
// ============================================================

export async function saveFile(
  file: Buffer,
  filename: string,
  mimeType: string
): Promise<ChatAttachment> {
  await ensureFilesDirectory();

  const id = generateId('file');
  const ext = path.extname(filename) || getExtensionFromMime(mimeType);
  const savedFilename = `${id}${ext}`;
  const filePath = path.join(FILES_DIR, savedFilename);

  await fs.writeFile(filePath, file);

  return {
    id,
    filename,
    mimeType,
    size: file.length,
    path: savedFilename,
    createdAt: new Date().toISOString(),
  };
}

export async function getFile(filename: string): Promise<Buffer | null> {
  try {
    const filePath = path.join(FILES_DIR, filename);
    return await fs.readFile(filePath);
  } catch {
    return null;
  }
}

export function getFileUrl(attachment: ChatAttachment): string {
  return `/api/files/${attachment.path}`;
}

function getExtensionFromMime(mimeType: string): string {
  const map: Record<string, string> = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'audio/webm': '.webm',
    'audio/mp3': '.mp3',
    'audio/mpeg': '.mp3',
    'audio/wav': '.wav',
    'audio/ogg': '.ogg',
    'video/mp4': '.mp4',
    'video/webm': '.webm',
    'application/pdf': '.pdf',
  };
  return map[mimeType] || '';
}
