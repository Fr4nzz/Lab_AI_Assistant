import Database from 'better-sqlite3'
import { drizzle, type BetterSQLite3Database } from 'drizzle-orm/better-sqlite3'
import { eq, desc, asc } from 'drizzle-orm'
import * as schema from '../db/schema'
import { mkdirSync, existsSync } from 'fs'
import { dirname, resolve } from 'path'

// Database singleton with proper typing
let _db: BetterSQLite3Database<typeof schema> | null = null

function getDbPath(): string {
  const config = useRuntimeConfig()
  return config.databasePath || './data/lab-assistant.db'
}

export function useDB() {
  if (!_db) {
    const dbPath = getDbPath()
    const absolutePath = resolve(process.cwd(), dbPath)

    // Ensure directory exists
    const dir = dirname(absolutePath)
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true })
    }

    const sqlite = new Database(absolutePath)
    sqlite.pragma('journal_mode = WAL')

    _db = drizzle(sqlite, { schema })

    // Run migrations on first connection
    initializeDatabase(sqlite)
  }
  return _db
}

function initializeDatabase(sqlite: Database.Database) {
  // Create tables if they don't exist
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      email TEXT NOT NULL,
      name TEXT,
      avatar TEXT,
      provider TEXT NOT NULL,
      provider_id TEXT NOT NULL,
      created_at INTEGER NOT NULL
    );

    CREATE UNIQUE INDEX IF NOT EXISTS users_provider_id_idx ON users(provider, provider_id);

    CREATE TABLE IF NOT EXISTS chats (
      id TEXT PRIMARY KEY,
      title TEXT,
      user_id TEXT,
      created_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS chats_user_id_idx ON chats(user_id);

    CREATE TABLE IF NOT EXISTS messages (
      id TEXT PRIMARY KEY,
      chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
      role TEXT NOT NULL,
      content TEXT,
      parts TEXT,
      created_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS messages_chat_id_idx ON messages(chat_id);

    CREATE TABLE IF NOT EXISTS files (
      id TEXT PRIMARY KEY,
      message_id TEXT REFERENCES messages(id) ON DELETE CASCADE,
      filename TEXT NOT NULL,
      mime_type TEXT NOT NULL,
      path TEXT NOT NULL,
      size INTEGER,
      created_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS files_message_id_idx ON files(message_id);

    CREATE TABLE IF NOT EXISTS user_settings (
      id TEXT PRIMARY KEY,
      visitor_id TEXT UNIQUE,
      user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
      chat_model TEXT DEFAULT 'gemini-3-flash-preview',
      main_thinking_level TEXT DEFAULT 'low',
      preprocessing_model TEXT DEFAULT 'gemini-flash-latest',
      preprocessing_thinking_level TEXT DEFAULT 'off',
      created_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS user_settings_visitor_id_idx ON user_settings(visitor_id);
    CREATE INDEX IF NOT EXISTS user_settings_user_id_idx ON user_settings(user_id);

    -- Migration: Add new columns if they don't exist (for existing databases)
    -- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we use a workaround
  `)

  // Add new columns if they don't exist (migration for existing databases)
  try {
    sqlite.exec(`ALTER TABLE user_settings ADD COLUMN main_thinking_level TEXT DEFAULT 'low'`)
  } catch {
    // Column already exists
  }
  try {
    sqlite.exec(`ALTER TABLE user_settings ADD COLUMN preprocessing_thinking_level TEXT DEFAULT 'off'`)
  } catch {
    // Column already exists
  }
  try {
    sqlite.exec(`ALTER TABLE user_settings ADD COLUMN enable_agent_logging INTEGER DEFAULT 0`)
  } catch {
    // Column already exists
  }
}

// ============================================================
// Chat Operations
// ============================================================

export async function getChats(userId?: string) {
  const db = useDB()

  const query = db
    .select()
    .from(schema.chats)
    .orderBy(desc(schema.chats.createdAt))

  if (userId) {
    return query.where(eq(schema.chats.userId, userId))
  }

  return query
}

export async function getChat(chatId: string) {
  const db = useDB()

  return db.query.chats.findFirst({
    where: eq(schema.chats.id, chatId),
    with: {
      messages: {
        orderBy: [asc(schema.messages.createdAt)]
      }
    }
  })
}

export async function createChat(data: { id?: string; title?: string; userId?: string }) {
  const db = useDB()

  const id = data.id || crypto.randomUUID()
  const now = new Date()

  await db.insert(schema.chats).values({
    id,
    title: data.title || null,
    userId: data.userId || null,
    createdAt: now
  })

  return { id, title: data.title, userId: data.userId, createdAt: now }
}

export async function updateChatTitle(chatId: string, title: string) {
  const db = useDB()

  await db
    .update(schema.chats)
    .set({ title })
    .where(eq(schema.chats.id, chatId))
}

export async function deleteChat(chatId: string) {
  const db = useDB()

  // Messages are deleted via CASCADE
  await db.delete(schema.chats).where(eq(schema.chats.id, chatId))
}

// ============================================================
// Message Operations
// ============================================================

export async function getMessages(chatId: string) {
  const db = useDB()

  return db
    .select()
    .from(schema.messages)
    .where(eq(schema.messages.chatId, chatId))
    .orderBy(asc(schema.messages.createdAt))
}

export async function addMessage(data: {
  id?: string
  chatId: string
  role: 'user' | 'assistant' | 'system'
  content?: string
  parts?: unknown[]
}) {
  const db = useDB()

  const id = data.id || crypto.randomUUID()
  const now = new Date()

  await db.insert(schema.messages).values({
    id,
    chatId: data.chatId,
    role: data.role,
    content: data.content || null,
    // Note: Don't JSON.stringify here - schema has mode: 'json' which handles serialization
    parts: data.parts || null,
    createdAt: now
  })

  return { id, ...data, createdAt: now }
}

// ============================================================
// User Operations
// ============================================================

export async function findOrCreateUser(data: {
  email: string
  name?: string
  avatar?: string
  provider: string
  providerId: string
}) {
  const db = useDB()

  // Check if user exists
  const existing = await db.query.users.findFirst({
    where: eq(schema.users.providerId, data.providerId)
  })

  if (existing) {
    // Update user info
    await db
      .update(schema.users)
      .set({
        name: data.name,
        avatar: data.avatar,
        email: data.email
      })
      .where(eq(schema.users.id, existing.id))

    return { ...existing, ...data }
  }

  // Create new user
  const id = crypto.randomUUID()
  const now = new Date()

  await db.insert(schema.users).values({
    id,
    email: data.email,
    name: data.name || null,
    avatar: data.avatar || null,
    provider: data.provider,
    providerId: data.providerId,
    createdAt: now
  })

  return { id, ...data, createdAt: now }
}

// ============================================================
// File Operations
// ============================================================

export async function saveFile(data: {
  messageId?: string
  filename: string
  mimeType: string
  path: string
  size?: number
}) {
  const db = useDB()

  const id = crypto.randomUUID()
  const now = new Date()

  await db.insert(schema.files).values({
    id,
    messageId: data.messageId || null,
    filename: data.filename,
    mimeType: data.mimeType,
    path: data.path,
    size: data.size || null,
    createdAt: now
  })

  return { id, ...data, createdAt: now }
}

export async function getFilesByMessage(messageId: string) {
  const db = useDB()

  return db
    .select()
    .from(schema.files)
    .where(eq(schema.files.messageId, messageId))
}

// ============================================================
// User Settings Operations
// ============================================================

export interface UserSettings {
  chatModel: string
  mainThinkingLevel: string  // For main chat model (Gemini 3: minimal/low/medium/high, Gemini 2.5: off/dynamic)
  preprocessingModel: string
  preprocessingThinkingLevel: string  // For image preprocessing
  enableAgentLogging: boolean  // For AI conversation logging (model evaluation)
}

const DEFAULT_SETTINGS: UserSettings = {
  chatModel: 'gemini-3-flash-preview',
  mainThinkingLevel: 'low',
  preprocessingModel: 'gemini-flash-latest',
  preprocessingThinkingLevel: 'off',  // Gemini 2.5 uses thinkingBudget: 'off' (0) or 'dynamic' (-1)
  enableAgentLogging: false
}

export async function getUserSettings(visitorId: string): Promise<UserSettings> {
  const db = useDB()

  const settings = await db.query.userSettings.findFirst({
    where: eq(schema.userSettings.visitorId, visitorId)
  })

  if (settings) {
    return {
      chatModel: settings.chatModel || DEFAULT_SETTINGS.chatModel,
      mainThinkingLevel: settings.mainThinkingLevel || DEFAULT_SETTINGS.mainThinkingLevel,
      preprocessingModel: settings.preprocessingModel || DEFAULT_SETTINGS.preprocessingModel,
      preprocessingThinkingLevel: settings.preprocessingThinkingLevel || DEFAULT_SETTINGS.preprocessingThinkingLevel,
      enableAgentLogging: settings.enableAgentLogging ?? DEFAULT_SETTINGS.enableAgentLogging
    }
  }

  return { ...DEFAULT_SETTINGS }
}

export async function updateUserSettings(
  visitorId: string,
  updates: Partial<UserSettings>
): Promise<UserSettings> {
  const db = useDB()

  // Check if settings exist
  const existing = await db.query.userSettings.findFirst({
    where: eq(schema.userSettings.visitorId, visitorId)
  })

  if (existing) {
    // Update existing settings
    await db
      .update(schema.userSettings)
      .set({
        chatModel: updates.chatModel ?? existing.chatModel,
        mainThinkingLevel: updates.mainThinkingLevel ?? existing.mainThinkingLevel,
        preprocessingModel: updates.preprocessingModel ?? existing.preprocessingModel,
        preprocessingThinkingLevel: updates.preprocessingThinkingLevel ?? existing.preprocessingThinkingLevel,
        enableAgentLogging: updates.enableAgentLogging ?? existing.enableAgentLogging
      })
      .where(eq(schema.userSettings.id, existing.id))

    return {
      chatModel: updates.chatModel ?? existing.chatModel ?? DEFAULT_SETTINGS.chatModel,
      mainThinkingLevel: updates.mainThinkingLevel ?? existing.mainThinkingLevel ?? DEFAULT_SETTINGS.mainThinkingLevel,
      preprocessingModel: updates.preprocessingModel ?? existing.preprocessingModel ?? DEFAULT_SETTINGS.preprocessingModel,
      preprocessingThinkingLevel: updates.preprocessingThinkingLevel ?? existing.preprocessingThinkingLevel ?? DEFAULT_SETTINGS.preprocessingThinkingLevel,
      enableAgentLogging: updates.enableAgentLogging ?? existing.enableAgentLogging ?? DEFAULT_SETTINGS.enableAgentLogging
    }
  }

  // Create new settings
  const id = crypto.randomUUID()
  const now = new Date()

  await db.insert(schema.userSettings).values({
    id,
    visitorId,
    chatModel: updates.chatModel ?? DEFAULT_SETTINGS.chatModel,
    mainThinkingLevel: updates.mainThinkingLevel ?? DEFAULT_SETTINGS.mainThinkingLevel,
    preprocessingModel: updates.preprocessingModel ?? DEFAULT_SETTINGS.preprocessingModel,
    preprocessingThinkingLevel: updates.preprocessingThinkingLevel ?? DEFAULT_SETTINGS.preprocessingThinkingLevel,
    enableAgentLogging: updates.enableAgentLogging ?? DEFAULT_SETTINGS.enableAgentLogging,
    createdAt: now
  })

  return {
    chatModel: updates.chatModel ?? DEFAULT_SETTINGS.chatModel,
    mainThinkingLevel: updates.mainThinkingLevel ?? DEFAULT_SETTINGS.mainThinkingLevel,
    preprocessingModel: updates.preprocessingModel ?? DEFAULT_SETTINGS.preprocessingModel,
    preprocessingThinkingLevel: updates.preprocessingThinkingLevel ?? DEFAULT_SETTINGS.preprocessingThinkingLevel,
    enableAgentLogging: updates.enableAgentLogging ?? DEFAULT_SETTINGS.enableAgentLogging
  }
}
