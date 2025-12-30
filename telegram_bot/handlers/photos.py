"""Photo and media group handling for Telegram bot."""

import logging
from typing import Dict
from telegram import Update
from telegram.ext import ContextTypes

from ..keyboards import build_photo_options_keyboard
from ..services import BackendService

logger = logging.getLogger(__name__)

# Temporary storage for media groups (keyed by media_group_id)
media_groups: Dict[str, Dict] = {}


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photo messages."""
    message = update.message

    if message.media_group_id:
        # Part of an album - collect all photos
        await collect_media_group(update, context)
    else:
        # Single photo - process immediately
        await process_single_photo(update, context)


async def collect_media_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Collect photos from a media group (album)."""
    message = update.message
    group_id = message.media_group_id
    user_id = message.from_user.id

    # Initialize group if first photo
    if group_id not in media_groups:
        media_groups[group_id] = {
            "photos": [],
            "chat_id": message.chat_id,
            "user_id": user_id,
            "processed": False,
        }
        # Schedule processing after delay to collect all photos
        context.job_queue.run_once(
            process_media_group_job,
            when=1.5,  # Wait 1.5 seconds for all photos
            data={"group_id": group_id, "user_id": user_id},
            name=f"media_group_{group_id}"
        )

    # Download photo (highest resolution)
    try:
        photo = message.photo[-1]  # Last = highest resolution
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        media_groups[group_id]["photos"].append(bytes(photo_bytes))
        logger.info(f"Collected photo {len(media_groups[group_id]['photos'])} for group {group_id}")
    except Exception as e:
        logger.error(f"Failed to download photo: {e}")


async def process_media_group_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process collected media group after timeout."""
    job_data = context.job.data
    group_id = job_data["group_id"]
    user_id = job_data["user_id"]

    # Get and remove group data
    group_data = media_groups.pop(group_id, None)

    if not group_data or group_data.get("processed"):
        return

    group_data["processed"] = True
    photos = group_data["photos"]
    chat_id = group_data["chat_id"]

    if not photos:
        return

    logger.info(f"Processing media group {group_id} with {len(photos)} photos")

    # Store photos in user context for later use
    # Access via application's user_data
    app_user_data = context.application.user_data.setdefault(user_id, {})
    app_user_data["pending_images"] = photos
    app_user_data["pending_chat_id"] = None  # Will be set when user selects action

    # Get recent chats for keyboard (now async)
    backend = BackendService()
    try:
        recent_chats = await backend.get_recent_chats(limit=3)
    finally:
        await backend.close()

    # Build and send keyboard
    keyboard = build_photo_options_keyboard(recent_chats)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📸 Recibí {len(photos)} imagen(es). ¿Qué deseas hacer?",
        reply_markup=keyboard
    )


async def process_single_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a single photo immediately."""
    message = update.message
    user_id = message.from_user.id

    # Download photo
    try:
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()

        # Store in user context
        context.user_data["pending_images"] = [bytes(photo_bytes)]
        context.user_data["pending_chat_id"] = None

        # Get recent chats (now async)
        backend = BackendService()
        try:
            recent_chats = await backend.get_recent_chats(limit=3)
        finally:
            await backend.close()

        # Build and send keyboard
        keyboard = build_photo_options_keyboard(recent_chats)
        await message.reply_text(
            text="📸 Recibí la imagen. ¿Qué deseas hacer?",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Failed to process photo: {e}")
        await message.reply_text(
            "❌ Error al procesar la imagen. Por favor intenta de nuevo."
        )
