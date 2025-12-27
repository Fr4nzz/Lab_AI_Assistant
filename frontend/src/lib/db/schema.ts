/**
 * Drizzle ORM Schema for Lab Assistant AI
 *
 * SQLite-based with PostgreSQL-ready structure.
 * Uses text for UUIDs and JSON for flexibility.
 */

import { sqliteTable, text, integer } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';

// ============================================================
// USERS TABLE
// ============================================================
export const users = sqliteTable('users', {
  id: text('id').primaryKey(), // UUID
  email: text('email').notNull().unique(),
  name: text('name'),
  image: text('image'),
  createdAt: text('created_at')
    .notNull()
    .default(sql`(datetime('now'))`),
});

// ============================================================
// CHATS TABLE
// ============================================================
export const chats = sqliteTable('chats', {
  id: text('id').primaryKey(), // UUID with timestamp prefix
  userId: text('user_id').references(() => users.id, { onDelete: 'cascade' }),
  title: text('title').notNull().default('Nuevo Chat'),
  createdAt: text('created_at')
    .notNull()
    .default(sql`(datetime('now'))`),
  updatedAt: text('updated_at')
    .notNull()
    .default(sql`(datetime('now'))`),
});

// ============================================================
// MESSAGES TABLE
// ============================================================
export const messages = sqliteTable('messages', {
  id: text('id').primaryKey(), // UUID with timestamp prefix
  chatId: text('chat_id')
    .notNull()
    .references(() => chats.id, { onDelete: 'cascade' }),
  role: text('role', { enum: ['user', 'assistant', 'system'] }).notNull(),
  content: text('content').notNull().default(''),
  // Store raw content including parts as JSON for flexibility
  rawContent: text('raw_content', { mode: 'json' }),
  // Order index for proper message ordering
  orderIndex: integer('order_index').notNull().default(0),
  // Metadata (model, tokens, duration, etc.)
  metadata: text('metadata', { mode: 'json' }),
  createdAt: text('created_at')
    .notNull()
    .default(sql`(datetime('now'))`),
});

// ============================================================
// FILES TABLE (Attachments)
// ============================================================
export const files = sqliteTable('files', {
  id: text('id').primaryKey(), // UUID with timestamp prefix
  messageId: text('message_id')
    .notNull()
    .references(() => messages.id, { onDelete: 'cascade' }),
  filename: text('filename').notNull(),
  mimeType: text('mime_type').notNull(),
  path: text('path').notNull(), // Relative path in files directory
  size: integer('size').notNull().default(0),
  createdAt: text('created_at')
    .notNull()
    .default(sql`(datetime('now'))`),
});

// ============================================================
// TYPE EXPORTS
// ============================================================
export type User = typeof users.$inferSelect;
export type NewUser = typeof users.$inferInsert;

export type Chat = typeof chats.$inferSelect;
export type NewChat = typeof chats.$inferInsert;

export type Message = typeof messages.$inferSelect;
export type NewMessage = typeof messages.$inferInsert;

export type File = typeof files.$inferSelect;
export type NewFile = typeof files.$inferInsert;
