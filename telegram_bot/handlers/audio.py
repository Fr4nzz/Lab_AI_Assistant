"""Audio and voice message handling for Telegram bot."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..keyboards import build_audio_options_keyboard
from ..services import BackendService

logger = logging.getLogger(__name__)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming audio messages (voice notes and audio files).

    Telegram sends:
    - Voice notes as update.message.voice (OGG/Opus format)
    - Audio files as update.message.audio (MP3, M4A, etc.)
    """
    message = update.message

    # Determine audio type and get file
    if message.voice:
        # Voice note (recorded in Telegram)
        audio_file = message.voice
        mime_type = "audio/ogg"  # Telegram voice notes are OGG/Opus
        audio_type = "voice"
        logger.info(f"Received voice note: {audio_file.duration}s, {audio_file.file_size} bytes")
    elif message.audio:
        # Audio file (uploaded file)
        audio_file = message.audio
        mime_type = audio_file.mime_type or "audio/mpeg"
        audio_type = "audio"
        logger.info(f"Received audio file: {audio_file.title or 'untitled'}, {audio_file.mime_type}")
    else:
        logger.warning("handle_audio called but no audio found in message")
        return

    # Download the audio
    try:
        file = await context.bot.get_file(audio_file.file_id)
        audio_bytes = await file.download_as_bytearray()

        # Check if there are pending images to combine with audio
        pending_images = context.user_data.get("pending_images", [])
        has_pending_images = len(pending_images) > 0

        # Store audio in user context
        context.user_data["pending_audio"] = bytes(audio_bytes)
        context.user_data["pending_audio_mime"] = mime_type

        # Get the most recent chat to offer "Continuar en chat" option
        backend = BackendService()
        try:
            recent_chats = await backend.get_recent_chats(limit=1)
            last_chat = recent_chats[0] if recent_chats else None
        except Exception as e:
            logger.warning(f"Could not fetch recent chat: {e}")
            last_chat = None
        finally:
            await backend.close()

        # Build keyboard with appropriate options
        keyboard = build_audio_options_keyboard(
            has_images=has_pending_images,
            image_count=len(pending_images),
            last_chat=last_chat
        )

        # Build message text based on context
        if has_pending_images:
            emoji = "🎤" if audio_type == "voice" else "🎵"
            text = (
                f"{emoji} Recibí audio + {len(pending_images)} imagen(es).\n\n"
                "¿Qué deseas hacer?"
            )
        else:
            emoji = "🎤" if audio_type == "voice" else "🎵"
            text = f"{emoji} Recibí el audio. ¿Qué deseas hacer?"

        await message.reply_text(text=text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Failed to process audio: {e}")
        await message.reply_text(
            "Error al procesar el audio. Por favor intenta de nuevo."
        )
