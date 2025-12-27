/**
 * Drizzle ORM Database Connection
 *
 * Uses better-sqlite3 for local development.
 * Can be swapped to libsql/client for Turso or PostgreSQL for production.
 */

import { drizzle, BetterSQLite3Database } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';
import path from 'path';
import { existsSync, mkdirSync } from 'fs';
import * as schema from './schema';

// Database file location
const DATA_DIR = path.join(process.cwd(), 'data');
const DB_PATH = path.join(DATA_DIR, 'lab-assistant.db');

// Lazy database instance
let _db: BetterSQLite3Database<typeof schema> | null = null;
let _sqlite: Database.Database | null = null;
let _initialized = false;

function ensureDataDir() {
  if (!existsSync(DATA_DIR)) {
    mkdirSync(DATA_DIR, { recursive: true });
  }
}

function getSqlite(): Database.Database {
  if (!_sqlite) {
    ensureDataDir();
    _sqlite = new Database(DB_PATH);
    _sqlite.pragma('journal_mode = WAL');
  }
  return _sqlite;
}

/**
 * Get the database instance (lazy initialization)
 */
export function getDb(): BetterSQLite3Database<typeof schema> {
  if (!_db) {
    const sqlite = getSqlite();
    _db = drizzle(sqlite, { schema });

    // Initialize tables on first access
    if (!_initialized) {
      initializeDb();
      _initialized = true;
    }
  }
  return _db;
}

// Export db as a getter for backward compatibility
export const db = new Proxy({} as BetterSQLite3Database<typeof schema>, {
  get(_, prop) {
    return (getDb() as unknown as Record<string, unknown>)[prop as string];
  },
});

// Export schema for convenience
export * from './schema';

// Helper to close the database (for cleanup)
export function closeDb() {
  if (_sqlite) {
    _sqlite.close();
    _sqlite = null;
    _db = null;
  }
}

// Initialize database tables
export function initializeDb() {
  const sqlite = getSqlite();

  // Create tables if they don't exist
  sqlite.exec(`
    -- Users table
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      email TEXT NOT NULL UNIQUE,
      name TEXT,
      image TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Chats table
    CREATE TABLE IF NOT EXISTS chats (
      id TEXT PRIMARY KEY,
      user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
      title TEXT NOT NULL DEFAULT 'Nuevo Chat',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Messages table
    CREATE TABLE IF NOT EXISTS messages (
      id TEXT PRIMARY KEY,
      chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
      role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
      content TEXT NOT NULL DEFAULT '',
      raw_content TEXT,
      order_index INTEGER NOT NULL DEFAULT 0,
      metadata TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Files table (attachments)
    CREATE TABLE IF NOT EXISTS files (
      id TEXT PRIMARY KEY,
      message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
      filename TEXT NOT NULL,
      mime_type TEXT NOT NULL,
      path TEXT NOT NULL,
      size INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Indexes for better query performance
    CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);
    CREATE INDEX IF NOT EXISTS idx_chats_created_at ON chats(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
    CREATE INDEX IF NOT EXISTS idx_messages_order ON messages(chat_id, order_index);
    CREATE INDEX IF NOT EXISTS idx_files_message_id ON files(message_id);
  `);
}
