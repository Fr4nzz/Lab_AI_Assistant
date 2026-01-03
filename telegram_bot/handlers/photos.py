"""Photo and media group handling for Telegram bot."""

import asyncio
import logging
import time
from typing import Dict, List
from telegram import Update
from telegram.ext import ContextTypes

from ..keyboards import build_photo_options_keyboard
from ..services import BackendService

logger = logging.getLogger(__name__)

# Temporary storage for media groups (keyed by media_group_id)
media_groups: Dict[str, Dict] = {}


async def prefetch_in_background(photos: List[bytes], user_data: dict) -> None:
    """
    Prefetch orders in background while user decides what to do.
    Results are stored in user_data for later use.

    Note: Image rotation is NOT done here - it's handled by the backend's
    image-rotation tool when the agent processes the message.
    """
    backend = BackendService()
    try:
        # Prefetch orders
        result = await backend.prefetch_orders()
        user_data["prefetch_orders_result"] = result
        user_data["prefetch_orders_timestamp"] = time.time()
        logger.info(f"[Prefetch] Orders ready: {result.get('freshness', {})}")

    except Exception as e:
        logger.error(f"[Prefetch] Background prefetch error: {e}")
    finally:
        await backend.close()


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
            "caption": message.caption,  # Capture caption from first photo
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
    caption = group_data.get("caption")

    if not photos:
        return

    logger.info(f"Processing media group {group_id} with {len(photos)} photos, caption: {caption[:30] if caption else 'None'}...")

    # Store photos and caption in user context for later use
    # Access via application's user_data
    app_user_data = context.application.user_data.setdefault(user_id, {})
    app_user_data["pending_images"] = photos
    app_user_data["pending_chat_id"] = None  # Will be set when user selects action
    app_user_data["pending_caption"] = caption  # Store caption for "caption" action

    # Start prefetch in background (orders)
    # This runs concurrently while user decides what to do
    asyncio.create_task(prefetch_in_background(photos, app_user_data))

    # Build keyboard (pass caption if present)
    keyboard = build_photo_options_keyboard(caption=caption)

    # Customize message based on whether caption was provided
    if caption:
        text = f"📸 Recibí {len(photos)} imagen(es) con mensaje. ¿Qué deseas hacer?"
    else:
        text = f"📸 Recibí {len(photos)} imagen(es). ¿Qué deseas hacer?"

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard
    )


async def process_single_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a single photo immediately."""
    message = update.message
    caption = message.caption

    # Download photo
    try:
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()

        # Store in user context (including caption)
        photos = [bytes(photo_bytes)]
        context.user_data["pending_images"] = photos
        context.user_data["pending_chat_id"] = None
        context.user_data["pending_caption"] = caption  # Store caption for "caption" action

        # Start prefetch in background (orders)
        # This runs concurrently while user decides what to do
        asyncio.create_task(prefetch_in_background(photos, context.user_data))

        # Build keyboard (pass caption if present)
        keyboard = build_photo_options_keyboard(caption=caption)

        # Customize message based on whether caption was provided
        if caption:
            text = "📸 Recibí la imagen con mensaje. ¿Qué deseas hacer?"
        else:
            text = "📸 Recibí la imagen. ¿Qué deseas hacer?"

        await message.reply_text(text=text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Failed to process photo: {e}")
        await message.reply_text(
            "❌ Error al procesar la imagen. Por favor intenta de nuevo."
        )
