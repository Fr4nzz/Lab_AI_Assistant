/**
 * Simple file-based database for chat messages and attachments.
 * Stores data as JSON files with file attachments in a separate directory.
 *
 * Structure:
 * - data/chats.json - List of all chats
 * - data/messages/{chatId}.json - Messages for each chat
 * - data/files/{fileId}.{ext} - Uploaded files
 */

import { promises as fs } from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';

// Generate timestamped ID: YYYYMMDD_HHMMSS_randomchars
function generateId(prefix?: string): string {
  const now = new Date();
  const timestamp = now.toISOString()
    .replace(/[-:T]/g, '')
    .replace(/\.\d{3}Z$/, '');  // 20251226183000
  const random = randomUUID().slice(0, 8);
  return prefix ? `${prefix}_${timestamp}_${random}` : `${timestamp}_${random}`;
}

// Data directory (relative to project root)
const DATA_DIR = path.join(process.cwd(), 'data');
const CHATS_FILE = path.join(DATA_DIR, 'chats.json');
const MESSAGES_DIR = path.join(DATA_DIR, 'messages');
const FILES_DIR = path.join(DATA_DIR, 'files');

// Types
export interface ChatAttachment {
  id: string;
  filename: string;
  mimeType: string;
  size: number;
  path: string;  // Relative path in files directory
  createdAt: string;
}

export interface ChatMessage {
  id: string;
  chatId: string;
  role: 'user' | 'assistant';
  content: string;  // Text content
  rawContent?: unknown;  // Full raw content including parts (for debugging)
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
}

// Initialize directories
async function ensureDirectories() {
  await fs.mkdir(DATA_DIR, { recursive: true });
  await fs.mkdir(MESSAGES_DIR, { recursive: true });
  await fs.mkdir(FILES_DIR, { recursive: true });
}

// Read JSON file safely
async function readJsonFile<T>(filePath: string, defaultValue: T): Promise<T> {
  try {
    const data = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(data);
  } catch {
    return defaultValue;
  }
}

// Write JSON file
async function writeJsonFile(filePath: string, data: unknown): Promise<void> {
  await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf-8');
}

// ============================================================
// CHATS
// ============================================================

export async function getChats(): Promise<Chat[]> {
  await ensureDirectories();
  return readJsonFile<Chat[]>(CHATS_FILE, []);
}

export async function getChat(id: string): Promise<Chat | null> {
  const chats = await getChats();
  return chats.find(c => c.id === id) || null;
}

export async function createChat(title: string = 'New Chat'): Promise<Chat> {
  await ensureDirectories();
  const chats = await getChats();

  const chat: Chat = {
    id: generateId('chat'),
    title,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messageCount: 0,
  };

  chats.unshift(chat);
  await writeJsonFile(CHATS_FILE, chats);

  return chat;
}

export async function updateChat(id: string, updates: Partial<Chat>): Promise<Chat | null> {
  const chats = await getChats();
  const index = chats.findIndex(c => c.id === id);

  if (index === -1) return null;

  chats[index] = {
    ...chats[index],
    ...updates,
    updatedAt: new Date().toISOString(),
  };

  await writeJsonFile(CHATS_FILE, chats);
  return chats[index];
}

export async function updateChatTitle(id: string, title: string): Promise<Chat | null> {
  return updateChat(id, { title });
}

export async function deleteChat(id: string): Promise<boolean> {
  const chats = await getChats();
  const filtered = chats.filter(c => c.id !== id);

  if (filtered.length === chats.length) return false;

  await writeJsonFile(CHATS_FILE, filtered);

  // Also delete messages file
  try {
    await fs.unlink(path.join(MESSAGES_DIR, `${id}.json`));
  } catch {
    // Ignore if file doesn't exist
  }

  return true;
}

// ============================================================
// MESSAGES
// ============================================================

export async function getMessages(chatId: string): Promise<ChatMessage[]> {
  await ensureDirectories();
  const messagesFile = path.join(MESSAGES_DIR, `${chatId}.json`);
  return readJsonFile<ChatMessage[]>(messagesFile, []);
}

export async function getMessage(chatId: string, messageId: string): Promise<ChatMessage | null> {
  const messages = await getMessages(chatId);
  return messages.find(m => m.id === messageId) || null;
}

export async function addMessage(
  chatId: string,
  role: 'user' | 'assistant',
  content: string,
  rawContent?: unknown,
  attachments: ChatAttachment[] = [],
  metadata?: ChatMessage['metadata']
): Promise<ChatMessage> {
  await ensureDirectories();

  const messages = await getMessages(chatId);

  const message: ChatMessage = {
    id: generateId('msg'),
    chatId,
    role,
    content,
    rawContent,
    attachments,
    createdAt: new Date().toISOString(),
    metadata,
  };

  messages.push(message);

  const messagesFile = path.join(MESSAGES_DIR, `${chatId}.json`);
  await writeJsonFile(messagesFile, messages);

  // Update chat message count
  await updateChat(chatId, { messageCount: messages.length });

  return message;
}

// ============================================================
// FILES
// ============================================================

export async function saveFile(
  file: Buffer,
  filename: string,
  mimeType: string
): Promise<ChatAttachment> {
  await ensureDirectories();

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

// ============================================================
// DEBUG HELPERS
// ============================================================

const DEBUG_DIR = path.join(DATA_DIR, 'debug');

export interface DebugRequest {
  id: string;
  chatId: string;
  timestamp: string;
  frontendMessages: unknown;  // Raw messages from frontend
  backendRequest: unknown;    // What was sent to backend (converted format)
  backendResponse?: string;   // Response from backend
  error?: string;
}

export async function saveDebugRequest(
  chatId: string,
  frontendMessages: unknown,
  backendRequest: unknown
): Promise<string> {
  await fs.mkdir(DEBUG_DIR, { recursive: true });

  const id = generateId('dbg');
  const debugRecord: DebugRequest = {
    id,
    chatId,
    timestamp: new Date().toISOString(),
    frontendMessages,
    backendRequest,
  };

  const filePath = path.join(DEBUG_DIR, `${chatId}_${id}.json`);
  await writeJsonFile(filePath, debugRecord);

  return id;
}

export async function updateDebugRequest(
  chatId: string,
  debugId: string,
  updates: { backendResponse?: string; error?: string }
): Promise<void> {
  const filePath = path.join(DEBUG_DIR, `${chatId}_${debugId}.json`);
  try {
    const record = await readJsonFile<DebugRequest>(filePath, {} as DebugRequest);
    const updated = { ...record, ...updates };
    await writeJsonFile(filePath, updated);
  } catch {
    // Ignore errors
  }
}

export async function getDebugRequests(chatId: string): Promise<DebugRequest[]> {
  await fs.mkdir(DEBUG_DIR, { recursive: true });

  try {
    const files = await fs.readdir(DEBUG_DIR);
    const chatFiles = files.filter(f => f.startsWith(`${chatId}_`) && f.endsWith('.json'));

    const requests: DebugRequest[] = [];
    for (const file of chatFiles) {
      const filePath = path.join(DEBUG_DIR, file);
      const record = await readJsonFile<DebugRequest>(filePath, {} as DebugRequest);
      if (record.id) {
        requests.push(record);
      }
    }

    return requests.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  } catch {
    return [];
  }
}

export async function getAllMessagesForDebug(chatId: string): Promise<{
  chat: Chat | null;
  messages: ChatMessage[];
  debugRequests: DebugRequest[];
}> {
  const chat = await getChat(chatId);
  const messages = await getMessages(chatId);
  const debugRequests = await getDebugRequests(chatId);
  return { chat, messages, debugRequests };
}
