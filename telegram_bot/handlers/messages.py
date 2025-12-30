"""Text message handler for Telegram bot."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..keyboards import build_post_response_keyboard
from ..services import BackendService
from ..utils import build_chat_url

logger = logging.getLogger(__name__)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    message = update.message
    text = message.text

    # Check if we're waiting for a custom prompt
    if context.user_data.get("awaiting_prompt"):
        await handle_custom_prompt(update, context, text)
        return

    # Check if we're in follow-up mode
    if context.user_data.get("current_chat_id"):
        await handle_follow_up(update, context, text)
        return

    # Otherwise, create a new chat with the text message
    await handle_new_text_chat(update, context, text)


async def handle_custom_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    """Handle custom prompt input after user selected 'Escribe el prompt'."""
    message = update.message

    # Get pending data
    images = context.user_data.get("pending_images", [])
    chat_id = context.user_data.get("pending_chat_id")

    # Clear the awaiting flag
    context.user_data["awaiting_prompt"] = False

    # Create new chat if needed
    backend = BackendService()
    if not chat_id:
        chat_id = backend.create_chat(title=prompt[:50])
        if not chat_id:
            await message.reply_text("❌ Error al crear el chat.")
            return

    context.user_data["current_chat_id"] = chat_id

    # Send processing message
    processing_msg = await message.reply_text("⏳ Procesando...")

    # Send to backend with tool notifications
    tools_used = []

    async def on_tool(tool_display: str):
        tools_used.append(tool_display)
        try:
            await processing_msg.edit_text(f"⏳ Procesando...\n\n{tool_display}")
        except Exception:
            pass  # Ignore edit errors

    response_text, tools = await backend.send_message(
        chat_id=chat_id,
        message=prompt,
        images=images,
        on_tool_call=on_tool
    )

    # Clear pending images
    context.user_data["pending_images"] = []

    # Update chat title if it was generic
    if prompt:
        backend.update_chat_title(chat_id, prompt[:50])

    # Send response
    await send_ai_response(processing_msg, response_text, chat_id, tools)


async def handle_follow_up(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle follow-up message in current chat."""
    message = update.message
    chat_id = context.user_data.get("current_chat_id")

    if not chat_id:
        await message.reply_text("No hay chat activo. Envía una foto para comenzar.")
        return

    # Send processing message
    processing_msg = await message.reply_text("⏳ Procesando...")

    # Send to backend
    backend = BackendService()
    tools_used = []

    async def on_tool(tool_display: str):
        tools_used.append(tool_display)
        try:
            await processing_msg.edit_text(f"⏳ Procesando...\n\n{tool_display}")
        except Exception:
            pass

    response_text, tools = await backend.send_message(
        chat_id=chat_id,
        message=text,
        images=None,
        on_tool_call=on_tool
    )

    # Send response
    await send_ai_response(processing_msg, response_text, chat_id, tools)


async def handle_new_text_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle text message that starts a new chat (no images)."""
    message = update.message

    # Create new chat
    backend = BackendService()
    chat_id = backend.create_chat(title=text[:50])

    if not chat_id:
        await message.reply_text("❌ Error al crear el chat.")
        return

    context.user_data["current_chat_id"] = chat_id

    # Send processing message
    processing_msg = await message.reply_text("⏳ Procesando...")

    # Send to backend
    tools_used = []

    async def on_tool(tool_display: str):
        tools_used.append(tool_display)
        try:
            await processing_msg.edit_text(f"⏳ Procesando...\n\n{tool_display}")
        except Exception:
            pass

    response_text, tools = await backend.send_message(
        chat_id=chat_id,
        message=text,
        images=None,
        on_tool_call=on_tool
    )

    # Send response
    await send_ai_response(processing_msg, response_text, chat_id, tools)


async def send_ai_response(processing_msg, response_text: str, chat_id: str, tools: list) -> None:
    """Send AI response with chat URL and post-response options."""
    # Build chat URL
    chat_url = build_chat_url(chat_id)

    # Format tools used
    tools_text = ""
    if tools:
        tools_text = "\n\n🔧 *Herramientas usadas:*\n" + "\n".join(f"  • {t}" for t in tools[:5])

    # Truncate response if too long (Telegram limit is 4096)
    max_len = 3500  # Leave room for URL and formatting
    if len(response_text) > max_len:
        response_text = response_text[:max_len] + "...\n\n_(Respuesta truncada)_"

    # Build full message
    full_text = (
        f"{response_text}"
        f"{tools_text}\n\n"
        f"🔗 *Ver en web:*\n{chat_url}"
    )

    # Edit the processing message with response
    try:
        keyboard = build_post_response_keyboard()
        await processing_msg.edit_text(
            text=full_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        # If edit fails (e.g., message too old), send new message
        logger.warning(f"Failed to edit message: {e}")
        keyboard = build_post_response_keyboard()
        await processing_msg.reply_text(
            text=full_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
