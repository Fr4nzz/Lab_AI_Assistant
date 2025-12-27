/**
 * Migration script to migrate existing JSON data to SQLite database.
 *
 * Usage: npx tsx src/lib/db/migrate.ts
 */

import { promises as fs } from 'fs';
import path from 'path';
import { eq } from 'drizzle-orm';
import { db, initializeDb, chats, messages, files } from './drizzle';

const DATA_DIR = path.join(process.cwd(), 'data');
const CHATS_FILE = path.join(DATA_DIR, 'chats.json');
const MESSAGES_DIR = path.join(DATA_DIR, 'messages');

interface LegacyChat {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

interface LegacyAttachment {
  id: string;
  filename: string;
  mimeType: string;
  size: number;
  path: string;
  createdAt: string;
}

interface LegacyMessage {
  id: string;
  chatId: string;
  role: 'user' | 'assistant';
  content: string;
  rawContent?: unknown;
  attachments: LegacyAttachment[];
  createdAt: string;
  metadata?: {
    model?: string;
    tokens?: number;
    duration?: number;
  };
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function readJsonFile<T>(filePath: string): Promise<T | null> {
  try {
    const data = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(data);
  } catch {
    return null;
  }
}

async function migrateData() {
  console.log('🔄 Starting migration...\n');

  // Initialize database tables
  console.log('📦 Initializing database tables...');
  initializeDb();
  console.log('✅ Database tables created\n');

  // Check if legacy data exists
  const hasLegacyChats = await fileExists(CHATS_FILE);

  if (!hasLegacyChats) {
    console.log('ℹ️  No legacy data found (data/chats.json does not exist)');
    console.log('✅ Migration complete - database is ready for fresh data\n');
    return;
  }

  // Read legacy chats
  console.log('📖 Reading legacy chats...');
  const legacyChats = await readJsonFile<LegacyChat[]>(CHATS_FILE);

  if (!legacyChats || legacyChats.length === 0) {
    console.log('ℹ️  No chats found in legacy data');
    console.log('✅ Migration complete\n');
    return;
  }

  console.log(`   Found ${legacyChats.length} chats to migrate\n`);

  let migratedChats = 0;
  let migratedMessages = 0;
  let migratedFiles = 0;

  for (const legacyChat of legacyChats) {
    try {
      // Check if chat already exists
      const existing = await db.select().from(chats).where(eq(chats.id, legacyChat.id)).limit(1);
      if (existing.length > 0) {
        console.log(`   ⏭️  Skipping chat ${legacyChat.id} (already exists)`);
        continue;
      }

      // Insert chat
      await db.insert(chats).values({
        id: legacyChat.id,
        title: legacyChat.title,
        createdAt: legacyChat.createdAt,
        updatedAt: legacyChat.updatedAt,
      });
      migratedChats++;

      // Read legacy messages for this chat
      const messagesFile = path.join(MESSAGES_DIR, `${legacyChat.id}.json`);
      const legacyMessages = await readJsonFile<LegacyMessage[]>(messagesFile);

      if (legacyMessages && legacyMessages.length > 0) {
        for (let i = 0; i < legacyMessages.length; i++) {
          const msg = legacyMessages[i];

          // Insert message
          await db.insert(messages).values({
            id: msg.id,
            chatId: msg.chatId,
            role: msg.role,
            content: msg.content,
            rawContent: msg.rawContent ? JSON.stringify(msg.rawContent) : null,
            orderIndex: i,
            metadata: msg.metadata ? JSON.stringify(msg.metadata) : null,
            createdAt: msg.createdAt,
          });
          migratedMessages++;

          // Insert attachments
          for (const attachment of msg.attachments) {
            await db.insert(files).values({
              id: attachment.id,
              messageId: msg.id,
              filename: attachment.filename,
              mimeType: attachment.mimeType,
              path: attachment.path,
              size: attachment.size,
              createdAt: attachment.createdAt,
            });
            migratedFiles++;
          }
        }
      }

      console.log(`   ✅ Migrated chat: ${legacyChat.title.slice(0, 30)}...`);
    } catch (error) {
      console.error(`   ❌ Failed to migrate chat ${legacyChat.id}:`, error);
    }
  }

  console.log('\n📊 Migration Summary:');
  console.log(`   Chats migrated: ${migratedChats}`);
  console.log(`   Messages migrated: ${migratedMessages}`);
  console.log(`   Files migrated: ${migratedFiles}`);
  console.log('\n✅ Migration complete!\n');

  // Optionally backup legacy files
  const backupDir = path.join(DATA_DIR, 'legacy-backup');
  console.log(`💡 Tip: Legacy JSON files are still in ${DATA_DIR}`);
  console.log(`   You can delete them or move to ${backupDir} after verifying migration\n`);
}

// Run migration
migrateData().catch(console.error);
