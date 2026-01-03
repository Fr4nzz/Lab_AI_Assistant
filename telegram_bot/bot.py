#!/usr/bin/env python
"""
Telegram bot for Lab Assistant.

This bot allows users to interact with Lab Assistant via Telegram,
supporting image uploads, multiple chat threads, and real-time tool notifications.

Usage:
    python -m telegram_bot.bot

Environment Variables:
    TELEGRAM_BOT_TOKEN: Bot token from @BotFather (required)
    TELEGRAM_ALLOWED_USERS: Comma-separated user IDs to allow (optional)
    BACKEND_URL: Backend API URL (default: http://localhost:8000)
    CLOUDFLARE_TUNNEL_URL: Cloudflare tunnel URL for chat links (optional)
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Windows asyncio fix - must be set before any async code runs
# The default ProactorEventLoop on Windows has issues with python-telegram-bot
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.error import NetworkError, TimedOut

from telegram_bot.handlers import (
    start,
    help_command,
    chats_command,
    cancel,
    model_command,
    update_command,
    handle_photo,
    handle_text,
    handle_callback,
)
from telegram_bot.handlers.commands import new_command

# Load environment from root .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# Reduce noise from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def get_allowed_users() -> set:
    """Get set of allowed Telegram user IDs from environment."""
    allowed = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
    if not allowed:
        return set()  # Empty = allow all

    try:
        return {int(uid.strip()) for uid in allowed.split(",") if uid.strip()}
    except ValueError:
        logger.warning("Invalid TELEGRAM_ALLOWED_USERS format, allowing all users")
        return set()


def create_user_filter(allowed_users: set):
    """Create a filter for allowed users."""
    if not allowed_users:
        return filters.ALL  # Allow all if no restriction

    return filters.User(user_id=list(allowed_users))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors gracefully, especially network errors during sleep/wake cycles."""
    error = context.error

    # Network errors are expected during laptop sleep/wake or tunnel restarts
    if isinstance(error, (NetworkError, TimedOut)):
        # Log at INFO level since this is expected behavior
        logger.info(f"Network interruption (expected during sleep/tunnel restart): {type(error).__name__}")
        return

    # For other errors, log as warning with details
    logger.warning(f"Update {update} caused error: {error}", exc_info=context.error)


def main() -> None:
    """Start the Telegram bot."""
    # Get bot token
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error(
            "TELEGRAM_BOT_TOKEN not set!\n"
            "Please add it to your .env file:\n"
            "  TELEGRAM_BOT_TOKEN=your_token_here\n\n"
            "Get a token from @BotFather on Telegram."
        )
        sys.exit(1)

    # Get allowed users
    allowed_users = get_allowed_users()
    if allowed_users:
        logger.info(f"Restricting bot to {len(allowed_users)} allowed users")
    else:
        logger.info("Bot is open to all users (no TELEGRAM_ALLOWED_USERS set)")

    # Create user filter
    user_filter = create_user_filter(allowed_users)

    # Create application with job queue for media groups
    app = Application.builder().token(token).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start, filters=user_filter))
    app.add_handler(CommandHandler("help", help_command, filters=user_filter))
    app.add_handler(CommandHandler("chats", chats_command, filters=user_filter))
    app.add_handler(CommandHandler("new", new_command, filters=user_filter))
    app.add_handler(CommandHandler("model", model_command, filters=user_filter))
    app.add_handler(CommandHandler("actualizar", update_command, filters=user_filter))
    app.add_handler(CommandHandler("update", update_command, filters=user_filter))
    app.add_handler(CommandHandler("cancel", cancel, filters=user_filter))

    # Register photo handler (for single photos and albums)
    app.add_handler(MessageHandler(
        filters.PHOTO & user_filter,
        handle_photo
    ))

    # Register text message handler
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & user_filter,
        handle_text
    ))

    # Register callback query handler for inline keyboards
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Register error handler for graceful error handling
    app.add_error_handler(error_handler)

    # Log startup info
    logger.info("=" * 50)
    logger.info("Lab Assistant Telegram Bot Starting...")
    logger.info("=" * 50)
    logger.info(f"Backend URL: {os.environ.get('BACKEND_URL', 'http://localhost:8000')}")

    # Check for Cloudflare URL (env var or file)
    from telegram_bot.utils.urls import get_cloudflare_url
    cloudflare_url = get_cloudflare_url()
    if cloudflare_url:
        logger.info(f"Cloudflare URL: {cloudflare_url}")
    else:
        logger.info("Cloudflare URL: Not set (will check file at runtime)")

    logger.info("")
    logger.info("Bot is running. Press Ctrl+C to stop.")
    logger.info("")

    # Start polling
    # drop_pending_updates=True: Ignore messages sent while bot was offline
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
