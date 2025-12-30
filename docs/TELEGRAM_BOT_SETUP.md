# Telegram Bot Setup Guide

This guide explains how to create a Telegram bot for Lab Assistant and share it with other users.

---

## Table of Contents

1. [Create Your Bot](#step-1-create-your-bot-with-botfather)
2. [Configure the Bot](#step-2-configure-your-bot)
3. [Run the Bot](#step-3-run-the-bot)
4. [Share with Others](#step-4-share-your-bot-with-others)
5. [Restrict Access](#step-5-restrict-access-optional)
6. [Troubleshooting](#troubleshooting)

---

## Step 1: Create Your Bot with BotFather

BotFather is Telegram's official bot for creating and managing bots.

### 1.1 Start BotFather

1. Open Telegram
2. Search for `@BotFather` or click: https://t.me/BotFather
3. Click **Start** or send `/start`

### 1.2 Create a New Bot

1. Send `/newbot` to BotFather
2. Enter a **name** for your bot (displayed in chats):
   ```
   Lab Assistant
   ```
3. Enter a **username** (must end in `bot`):
   ```
   MiLabAssistant_bot
   ```
   > Note: Username must be unique across all of Telegram

4. BotFather will send you a message with your **API token**:
   ```
   Done! Congratulations on your new bot. You will find it at t.me/MiLabAssistant_bot.

   Use this token to access the HTTP API:
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

   Keep your token secure and store it safely.
   ```

5. **Copy the token** - you'll need it in the next step

### 1.3 Customize Your Bot (Optional)

Send these commands to BotFather:

```
/setdescription
```
> Enter: "Bot para Lab Assistant - Envía fotos para cotizar o pasar datos al sistema de laboratorio"

```
/setabouttext
```
> Enter: "Asistente de laboratorio con IA. Envía una foto para comenzar."

```
/setuserpic
```
> Send a profile picture for your bot

```
/setcommands
```
> Enter:
> ```
> start - Iniciar el bot
> help - Mostrar ayuda
> chats - Ver chats recientes
> new - Crear nuevo chat
> cancel - Cancelar operación
> ```

---

## Step 2: Configure Your Bot

### 2.1 Add Token to .env

Open your `.env` file and add the token:

```bash
# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 2.2 Optional: Restrict Users

To restrict the bot to specific users:

1. **Find your Telegram User ID:**
   - Message `@userinfobot` on Telegram
   - It will reply with your user ID (e.g., `123456789`)

2. **Add to .env:**
   ```bash
   # Only allow specific users (comma-separated)
   TELEGRAM_ALLOWED_USERS=123456789,987654321
   ```

3. **Leave empty to allow all:**
   ```bash
   TELEGRAM_ALLOWED_USERS=
   ```

### 2.3 Optional: Set Cloudflare URL

If you're using Cloudflare tunnel, add the URL:

```bash
CLOUDFLARE_TUNNEL_URL=https://your-tunnel.trycloudflare.com
```

This allows the bot to generate clickable links to view chats in the web UI.

---

## Step 3: Run the Bot

### 3.1 Start the Backend First

The bot requires the backend to be running:

```batch
.\start-dev.bat
```

### 3.2 Start the Telegram Bot

In a new terminal:

```batch
.\start-telegram-bot.bat
```

Or manually:

```bash
python -m telegram_bot.bot
```

### 3.3 Verify It's Working

1. Open Telegram
2. Search for your bot's username (e.g., `@MiLabAssistant_bot`)
3. Click **Start**
4. Send a photo - you should see options appear!

---

## Step 4: Share Your Bot with Others

### Option A: Direct Link

Share the link to your bot:

```
https://t.me/MiLabAssistant_bot
```

Replace `MiLabAssistant_bot` with your bot's username.

### Option B: QR Code

1. Go to your bot in Telegram
2. Tap the bot's name at the top
3. Tap **Share** → Copy link or show QR code

### Option C: Search

Tell others to search for your bot's username in Telegram:

```
@MiLabAssistant_bot
```

---

## Step 5: Restrict Access (Optional)

### Method 1: User ID Whitelist

Add specific user IDs to `.env`:

```bash
TELEGRAM_ALLOWED_USERS=123456789,987654321,111222333
```

To find someone's user ID:
1. Have them message `@userinfobot`
2. They'll receive their ID
3. Add it to the list

### Method 2: Keep Bot Private

Don't share the username publicly. Only share with intended users directly.

### Method 3: Bot Privacy Settings

Message BotFather:

```
/setjoingroups
```
> Select your bot, then choose **Disable** to prevent adding to groups

---

## How Users Use the Bot

### Sending Photos

1. **Single Photo:** Just send a photo
2. **Multiple Photos:** Send as album (select multiple before sending)

### Workflow

```
User sends photo(s)
        ↓
┌────────────────────────────────┐
│ 📝 Nuevo chat: Cotizar         │
│ 📋 Nuevo chat: Pasar datos     │
│ ✏️ Nuevo chat: Escribe prompt  │
│ ─────────────────────────      │
│ 💬 Continuar en: Chat 1        │
│ 💬 Continuar en: Chat 2        │
└────────────────────────────────┘
        ↓
   AI processes and responds
        ↓
   Shows link to web UI
        ↓
┌────────────────────────────────┐
│ 💬 Seguir | ➕ Nuevo | 📂 Ver  │
└────────────────────────────────┘
```

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize the bot |
| `/help` | Show help message |
| `/chats` | List recent chats |
| `/new` | Start a new chat |
| `/cancel` | Cancel current operation |

---

## Troubleshooting

### Bot doesn't respond

1. **Check token:** Verify `TELEGRAM_BOT_TOKEN` in `.env` is correct
2. **Check backend:** Make sure `start-dev.bat` is running
3. **Check logs:** Look at the terminal running the bot for errors

### "User not allowed" error

Add the user's ID to `TELEGRAM_ALLOWED_USERS` in `.env`

### Photos not processing

1. Ensure backend is running on port 8000
2. Check backend logs for errors
3. Verify Gemini API keys are set

### Links show localhost

Set `CLOUDFLARE_TUNNEL_URL` in `.env` if using tunnel, or ensure local network is accessible.

### Bot is slow

AI processing can take 10-30 seconds. The bot shows tool usage while processing.

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Telegram App   │────▶│  Telegram Bot    │────▶│  Backend API    │
│  (User's phone) │     │  (telegram_bot/) │     │  (port 8000)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │                        │
                                │                        ▼
                                │               ┌──────────────────┐
                                ▼               │  Gemini AI       │
                        ┌──────────────────┐    └──────────────────┘
                        │  SQLite DB       │
                        │  (shared with    │
                        │   web UI)        │
                        └──────────────────┘
```

---

## Security Notes

1. **Keep your token secret** - Anyone with the token can control your bot
2. **Use user restrictions** - Set `TELEGRAM_ALLOWED_USERS` for sensitive data
3. **Bot sees all photos** - Users should only send work-related images
4. **Data is stored locally** - Chat history is in `data/lab-assistant.db`

---

## Updating the Bot

When you update Lab Assistant:

1. Stop the Telegram bot (Ctrl+C)
2. Pull updates: `git pull`
3. Restart: `.\start-telegram-bot.bat`

The bot will automatically reconnect to Telegram.
