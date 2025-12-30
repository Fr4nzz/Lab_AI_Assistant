# Telegram Bot Integration Plan

## Overview

This document outlines the implementation plan for a Telegram bot that allows users to interact with the Lab Assistant from their mobile phones. The bot will support sending images (photos of notebooks, documents) and managing multiple chat threads similar to the web UI.

---

## User Flow Design

### 1. Initial Photo/Message Flow

```
User sends photo(s) of notebook
         │
         ▼
┌─────────────────────────────────────────────┐
│  Bot responds with inline keyboard:         │
│                                             │
│  📝 Nuevo chat: Cotizar                     │
│  📋 Nuevo chat: Pasar datos                 │
│  ✏️  Nuevo chat: Escribe el prompt          │
│  ─────────────────────────────              │
│  💬 Continuar en: [Chat 1 title]            │
│  💬 Continuar en: [Chat 2 title]            │
│  💬 Continuar en: [Chat 3 title]            │
└─────────────────────────────────────────────┘
```

### 2. After Selecting "Nuevo chat" with Predefined Prompt

```
User taps "Nuevo chat: Cotizar"
         │
         ▼
Bot creates new chat, sends image + "cotizar" prompt to AI
         │
         ▼
Bot streams/sends AI response
         │
         ▼
┌─────────────────────────────────────────────┐
│  Bot shows post-response options:           │
│                                             │
│  💬 Seguir conversación                     │
│  ➕ Nuevo chat                              │
│  📂 Seleccionar chat                        │
└─────────────────────────────────────────────┘
```

### 3. After Selecting "Escribe el prompt"

```
User taps "Nuevo chat: Escribe el prompt"
         │
         ▼
Bot: "Escribe el prompt para acompañar la(s) imagen(es):"
         │
         ▼
User types custom prompt
         │
         ▼
Bot creates new chat, sends image + custom prompt to AI
         │
         ▼
(Same post-response flow as above)
```

### 4. After Selecting "Continuar en: [Chat]"

```
User taps "Continuar en: Cotización Juan"
         │
         ▼
┌─────────────────────────────────────────────┐
│  Bot shows prompt options for this chat:    │
│                                             │
│  📝 Cotizar                                 │
│  📋 Pasar datos                             │
│  ✏️  Escribe el prompt                      │
└─────────────────────────────────────────────┘
         │
         ▼
User selects prompt type → AI response → post-response options
```

---

## Technical Architecture

### Components

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Telegram Bot   │────▶│  Backend API     │────▶│  SQLite DB      │
│  (Python)       │     │  (FastAPI)       │     │  (Shared)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │
        │                        ▼
        │               ┌──────────────────┐
        │               │  Gemini API      │
        │               └──────────────────┘
        ▼
┌─────────────────┐
│  Telegram API   │
└─────────────────┘
```

### File Structure

```
Lab_AI_Assistant/
├── telegram_bot/
│   ├── __init__.py
│   ├── bot.py              # Main bot application
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── commands.py     # /start, /help, /chats, /new commands
│   │   ├── photos.py       # Photo/media group handling
│   │   ├── messages.py     # Text message handling
│   │   └── callbacks.py    # Inline button callbacks
│   ├── keyboards/
│   │   ├── __init__.py
│   │   └── inline.py       # Inline keyboard builders
│   ├── services/
│   │   ├── __init__.py
│   │   ├── backend.py      # Backend API client
│   │   └── media.py        # Media download/processing
│   └── utils/
│       ├── __init__.py
│       └── states.py       # User state management
├── start-telegram-bot.bat  # Windows launcher
└── .env                    # Add TELEGRAM_BOT_TOKEN
```

---

## Research Findings & Best Practices

### 1. Python-Telegram-Bot Library (v20+)

**Source:** [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/en/v22.5/telegram.inlinekeyboardbutton.html)

- Use `python-telegram-bot` v20+ (async/await based)
- Version 20+ uses `asyncio` and `httpx` internally
- Always answer callback queries: `await query.answer()`

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # REQUIRED - acknowledge the button press
    await query.edit_message_text(text=f"Selected: {query.data}")
```

### 2. Inline Keyboards

**Source:** [InlineKeyboard Example](https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/inlinekeyboard.py)

**Best Practices:**
- Limit to 5-6 buttons per keyboard
- Use clear, concise labels
- Callback data limited to 64 bytes - use short codes

```python
keyboard = [
    [InlineKeyboardButton("📝 Cotizar", callback_data="new:cotizar")],
    [InlineKeyboardButton("📋 Pasar datos", callback_data="new:pasar")],
    [InlineKeyboardButton("✏️ Escribe prompt", callback_data="new:custom")],
]
reply_markup = InlineKeyboardMarkup(keyboard)
```

### 3. Callback Data Design

**Source:** [Arbitrary callback_data Wiki](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Arbitrary-callback_data)

**Pattern:** Use short prefixes to identify action type:

| Callback Data | Meaning |
|--------------|---------|
| `new:cotizar` | New chat with "cotizar" prompt |
| `new:pasar` | New chat with "pasar datos" prompt |
| `new:custom` | New chat with custom prompt |
| `cont:<chat_id>` | Continue in specific chat |
| `sel:prompt` | Show prompt selection |
| `post:follow` | Follow up in current chat |
| `post:new` | Create new chat |
| `post:select` | Show chat selection |

### 4. Photo Handling

**Source:** [Working with Files and Media](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Working-with-Files-and-Media)

```python
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get highest resolution photo
    photo = update.message.photo[-1]  # Last item = highest resolution

    # Download photo
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()

    # Convert to base64 for backend
    base64_image = base64.b64encode(photo_bytes).decode('utf-8')
```

### 5. Media Groups (Multiple Photos)

**Source:** [Media Group Wiki](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-requested-design-patterns#how-do-i-deal-with-a-media-group)

**Challenge:** Each photo in an album arrives as separate message with same `media_group_id`.

**Solution: Timer-based collection**

```python
# Store pending media groups
media_groups: Dict[str, Dict] = {}

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if message.media_group_id:
        group_id = message.media_group_id

        if group_id not in media_groups:
            media_groups[group_id] = {
                "photos": [],
                "chat_id": message.chat_id,
                "user_id": message.from_user.id,
            }
            # Schedule processing after delay
            context.job_queue.run_once(
                process_media_group,
                when=1.5,  # Wait 1.5 seconds for all photos
                data=group_id,
                name=f"media_group_{group_id}"
            )

        # Add photo to group
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        media_groups[group_id]["photos"].append(photo_bytes)
    else:
        # Single photo - process immediately
        await process_single_photo(update, context)

async def process_media_group(context: ContextTypes.DEFAULT_TYPE):
    group_id = context.job.data
    group_data = media_groups.pop(group_id, None)

    if group_data:
        # Process all collected photos
        photos = group_data["photos"]
        chat_id = group_data["chat_id"]
        # Show keyboard with options...
```

### 6. Conversation State Management

**Source:** [ConversationHandler Docs](https://docs.python-telegram-bot.org/en/v22.5/telegram.ext.conversationhandler.html)

**Using `context.user_data` for simple state:**

```python
# Store pending images and state
context.user_data["pending_images"] = [base64_image1, base64_image2]
context.user_data["selected_chat_id"] = None
context.user_data["awaiting_prompt"] = False
```

**Using ConversationHandler for complex flows:**

```python
from telegram.ext import ConversationHandler, MessageHandler, filters

# States
AWAITING_PROMPT = 1

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.PHOTO, handle_photo)],
    states={
        AWAITING_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_prompt)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_user=True,
    per_chat=True,
)
```

### 7. Backend Integration

**Current Backend API:**

The backend already supports multimodal messages. Send images in OpenAI format:

```python
import httpx

async def send_to_backend(chat_id: str, message: str, images: List[bytes]):
    content = []

    # Add images
    for img_bytes in images:
        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
        })

    # Add text
    if message:
        content.append({"type": "text", "text": message})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": content}],
                "stream": False,  # Or True for streaming
                "model": "gemini-2.0-flash",
            },
            headers={"x-thread-id": chat_id},
            timeout=120.0
        )
        return response.json()
```

### 8. Database Integration

**Shared SQLite Database:**

The bot should use the same database as the web UI (`data/lab-assistant.db`). The schema already exists:

- `chats` table: `id`, `title`, `user_id`, `created_at`
- `messages` table: `id`, `chat_id`, `role`, `content`, `parts`, `created_at`

**Option A: Direct database access** (simpler)
```python
import sqlite3

def get_recent_chats(limit=3):
    conn = sqlite3.connect("data/lab-assistant.db")
    cursor = conn.execute(
        "SELECT id, title FROM chats ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    return cursor.fetchall()
```

**Option B: Use backend API** (cleaner separation)
- Add new endpoints to backend for Telegram bot

---

## Implementation Plan

### Phase 1: Basic Setup

1. **Install dependencies**
   ```bash
   pip install python-telegram-bot[job-queue] httpx
   ```

2. **Create bot with @BotFather**
   - Get `TELEGRAM_BOT_TOKEN`
   - Add to `.env`

3. **Create basic bot structure**
   - Entry point `/start` command
   - Basic photo handler
   - Simple callback handler

### Phase 2: Photo Handling

1. **Single photo handling**
   - Receive photo
   - Download and convert to base64
   - Show option keyboard

2. **Media group handling**
   - Collect photos with same `media_group_id`
   - Timer-based processing
   - Show option keyboard after collection

### Phase 3: Chat Management

1. **Get recent chats**
   - Query database directly
   - Show in inline keyboard

2. **Create new chat**
   - Insert into database
   - Get new chat ID

3. **Continue existing chat**
   - Load chat history
   - Append new message

### Phase 4: AI Integration

1. **Send to backend**
   - Format request with images + text
   - Handle streaming (optional) or wait for response

2. **Display response**
   - Format AI response for Telegram
   - Handle long messages (4096 char limit)
   - Show post-response options

### Phase 5: Polish

1. **Error handling**
   - Network errors
   - API rate limits
   - Invalid states

2. **User experience**
   - Loading indicators
   - Cancel operations
   - Help command

---

## Callback Data Schema

```
Action Format: <action>:<param>

new:cotizar      → Create new chat, send with "cotizar"
new:pasar        → Create new chat, send with "pasar datos"
new:custom       → Create new chat, wait for custom prompt
cont:<chat_id>   → Continue in existing chat (max 10 chars for ID)
prompt:cotizar   → Use "cotizar" prompt (after selecting chat)
prompt:pasar     → Use "pasar datos" prompt
prompt:custom    → Wait for custom prompt
post:follow      → Follow up in same chat
post:new         → Create new chat (without images)
post:select      → Show chat selection
```

---

## Environment Variables

Add to `.env`:

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional: Restrict to specific Telegram user IDs
TELEGRAM_ALLOWED_USERS=123456789,987654321
```

---

## Code Skeleton

### bot.py (Main Entry Point)

```python
#!/usr/bin/env python
"""Telegram bot for Lab Assistant."""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from handlers.commands import start, help_command, chats_command
from handlers.photos import handle_photo
from handlers.messages import handle_text
from handlers.callbacks import handle_callback

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Start the bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set in .env")
        return

    # Create application
    app = Application.builder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("chats", chats_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Start polling
    logger.info("Starting Telegram bot...")
    app.run_polling()


if __name__ == "__main__":
    main()
```

### handlers/photos.py (Photo Handler)

```python
"""Photo and media group handling."""

import base64
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.backend import get_recent_chats
from keyboards.inline import build_photo_options_keyboard

# Temporary storage for media groups
media_groups: Dict[str, Dict] = {}


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photo messages."""
    message = update.message

    if message.media_group_id:
        # Part of an album - collect all photos
        await collect_media_group(update, context)
    else:
        # Single photo - process immediately
        await process_single_photo(update, context)


async def collect_media_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect photos from a media group."""
    message = update.message
    group_id = message.media_group_id

    if group_id not in media_groups:
        media_groups[group_id] = {
            "photos": [],
            "chat_id": message.chat_id,
            "message_id": message.message_id,
        }
        # Schedule processing after delay
        context.job_queue.run_once(
            process_media_group_job,
            when=1.5,
            data=group_id,
            name=f"media_group_{group_id}"
        )

    # Download photo
    photo = message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()
    media_groups[group_id]["photos"].append(bytes(photo_bytes))


async def process_media_group_job(context: ContextTypes.DEFAULT_TYPE):
    """Process collected media group after timeout."""
    group_id = context.job.data
    group_data = media_groups.pop(group_id, None)

    if not group_data:
        return

    photos = group_data["photos"]
    chat_id = group_data["chat_id"]

    # Store photos in user context for later
    context.application.user_data.setdefault(chat_id, {})["pending_images"] = photos

    # Get recent chats for keyboard
    recent_chats = await get_recent_chats(limit=3)

    # Build and send keyboard
    keyboard = build_photo_options_keyboard(recent_chats)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📸 Recibí {len(photos)} imagen(es). ¿Qué deseas hacer?",
        reply_markup=keyboard
    )


async def process_single_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process a single photo immediately."""
    message = update.message

    # Download photo
    photo = message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()

    # Store in user context
    user_id = message.from_user.id
    context.user_data["pending_images"] = [bytes(photo_bytes)]

    # Get recent chats
    recent_chats = await get_recent_chats(limit=3)

    # Build and send keyboard
    keyboard = build_photo_options_keyboard(recent_chats)
    await message.reply_text(
        text="📸 Recibí la imagen. ¿Qué deseas hacer?",
        reply_markup=keyboard
    )
```

### keyboards/inline.py (Keyboard Builders)

```python
"""Inline keyboard builders."""

from typing import List, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_photo_options_keyboard(recent_chats: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    """Build keyboard for photo options.

    Args:
        recent_chats: List of (chat_id, title) tuples
    """
    keyboard = [
        [InlineKeyboardButton("📝 Nuevo chat: Cotizar", callback_data="new:cotizar")],
        [InlineKeyboardButton("📋 Nuevo chat: Pasar datos", callback_data="new:pasar")],
        [InlineKeyboardButton("✏️ Nuevo chat: Escribe el prompt", callback_data="new:custom")],
    ]

    # Add recent chats if available
    if recent_chats:
        keyboard.append([InlineKeyboardButton("─── Continuar en chat ───", callback_data="noop")])
        for chat_id, title in recent_chats:
            # Truncate title and chat_id for callback data (64 byte limit)
            short_id = chat_id[:10]
            display_title = title[:25] + "..." if len(title) > 25 else title
            keyboard.append([
                InlineKeyboardButton(f"💬 {display_title}", callback_data=f"cont:{short_id}")
            ])

    return InlineKeyboardMarkup(keyboard)


def build_prompt_selection_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for selecting prompt type."""
    keyboard = [
        [InlineKeyboardButton("📝 Cotizar", callback_data="prompt:cotizar")],
        [InlineKeyboardButton("📋 Pasar datos", callback_data="prompt:pasar")],
        [InlineKeyboardButton("✏️ Escribe el prompt", callback_data="prompt:custom")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_post_response_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for post-response options."""
    keyboard = [
        [InlineKeyboardButton("💬 Seguir conversación", callback_data="post:follow")],
        [
            InlineKeyboardButton("➕ Nuevo chat", callback_data="post:new"),
            InlineKeyboardButton("📂 Seleccionar", callback_data="post:select"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_chat_selection_keyboard(chats: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    """Build keyboard for selecting from recent chats."""
    keyboard = []
    for chat_id, title in chats:
        short_id = chat_id[:10]
        display_title = title[:30] + "..." if len(title) > 30 else title
        keyboard.append([
            InlineKeyboardButton(f"💬 {display_title}", callback_data=f"sel:{short_id}")
        ])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)
```

---

## Testing Checklist

- [ ] Bot responds to /start
- [ ] Single photo triggers option keyboard
- [ ] Multiple photos (album) are collected correctly
- [ ] "Nuevo chat: Cotizar" creates chat and sends to AI
- [ ] "Escribe el prompt" waits for text input
- [ ] "Continuar en chat" shows prompt selection
- [ ] AI response is displayed correctly
- [ ] Post-response options work
- [ ] Long responses are split correctly (4096 char limit)
- [ ] Errors are handled gracefully

---

## References

1. [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/en/v22.5/)
2. [InlineKeyboard Example](https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/inlinekeyboard.py)
3. [ConversationHandler](https://docs.python-telegram-bot.org/en/v22.5/telegram.ext.conversationhandler.html)
4. [Working with Files and Media](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Working-with-Files-and-Media)
5. [Media Group Handling](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-requested-design-patterns)
6. [Arbitrary callback_data](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Arbitrary-callback_data)
7. [father-bot/chatgpt_telegram_bot](https://github.com/father-bot/chatgpt_telegram_bot)
8. [yym68686/ChatGPT-Telegram-Bot](https://github.com/yym68686/ChatGPT-Telegram-Bot)
