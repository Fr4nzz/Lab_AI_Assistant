import { sqliteTable, text, integer, index, uniqueIndex } from 'drizzle-orm/sqlite-core'
import { relations } from 'drizzle-orm'

const timestamps = {
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull().$defaultFn(() => new Date())
}

export const users = sqliteTable('users', {
  id: text('id').primaryKey().$defaultFn(() => crypto.randomUUID()),
  email: text('email').notNull(),
  name: text('name'),
  avatar: text('avatar'),
  provider: text('provider').notNull(), // 'google' or 'github'
  providerId: text('provider_id').notNull(),
  ...timestamps
}, table => [
  uniqueIndex('users_provider_id_idx').on(table.provider, table.providerId)
])

export const usersRelations = relations(users, ({ many }) => ({
  chats: many(chats)
}))

export const chats = sqliteTable('chats', {
  id: text('id').primaryKey().$defaultFn(() => crypto.randomUUID()),
  title: text('title'),
  userId: text('user_id'),
  ...timestamps
}, table => [
  index('chats_user_id_idx').on(table.userId)
])

export const chatsRelations = relations(chats, ({ one, many }) => ({
  user: one(users, {
    fields: [chats.userId],
    references: [users.id]
  }),
  messages: many(messages)
}))

export const messages = sqliteTable('messages', {
  id: text('id').primaryKey().$defaultFn(() => crypto.randomUUID()),
  chatId: text('chat_id').notNull().references(() => chats.id, { onDelete: 'cascade' }),
  role: text('role', { enum: ['user', 'assistant', 'system'] }).notNull(),
  content: text('content'), // Plain text content
  parts: text('parts', { mode: 'json' }), // Multimodal parts (JSON array)
  ...timestamps
}, table => [
  index('messages_chat_id_idx').on(table.chatId)
])

export const messagesRelations = relations(messages, ({ one, many }) => ({
  chat: one(chats, {
    fields: [messages.chatId],
    references: [chats.id]
  }),
  files: many(files)
}))

// File attachments table
export const files = sqliteTable('files', {
  id: text('id').primaryKey().$defaultFn(() => crypto.randomUUID()),
  messageId: text('message_id').references(() => messages.id, { onDelete: 'cascade' }),
  filename: text('filename').notNull(),
  mimeType: text('mime_type').notNull(),
  path: text('path').notNull(), // Relative path in data/files/
  size: integer('size'),
  ...timestamps
}, table => [
  index('files_message_id_idx').on(table.messageId)
])

export const filesRelations = relations(files, ({ one }) => ({
  message: one(messages, {
    fields: [files.messageId],
    references: [messages.id]
  })
}))

// User settings table - synced between frontend and telegram
export const userSettings = sqliteTable('user_settings', {
  id: text('id').primaryKey().$defaultFn(() => crypto.randomUUID()),
  visitorId: text('visitor_id').unique(), // For anonymous users (frontend visitorId or telegram user_id)
  userId: text('user_id').references(() => users.id, { onDelete: 'cascade' }),

  // Main chat model
  chatModel: text('chat_model').default('gemini-3-flash-preview'),

  // Preprocessing settings
  preprocessingModel: text('preprocessing_model').default('gemini-flash-lite-latest'),
  thinkingLevel: text('thinking_level').default('low'),

  ...timestamps
}, table => [
  index('user_settings_visitor_id_idx').on(table.visitorId),
  index('user_settings_user_id_idx').on(table.userId)
])

export const userSettingsRelations = relations(userSettings, ({ one }) => ({
  user: one(users, {
    fields: [userSettings.userId],
    references: [users.id]
  })
}))
