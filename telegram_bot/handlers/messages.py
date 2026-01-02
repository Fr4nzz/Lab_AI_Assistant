"""Text message handler for Telegram bot."""

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes

try:
    import telegramify_markdown
    HAS_TELEGRAMIFY = True
except ImportError:
    HAS_TELEGRAMIFY = False

from ..keyboards import build_post_response_keyboard, build_ask_user_keyboard, DEFAULT_MODEL
from ..services import BackendService, AskUserOptions
from ..utils import build_chat_url

logger = logging.getLogger(__name__)


def convert_tables_to_code_blocks(text: str) -> str:
    """
    Convert Markdown tables to code blocks for Telegram display.

    Telegram doesn't support tables natively, so we wrap them in
    code blocks to preserve alignment with monospace font.
    """
    lines = text.split('\n')
    result = []
    table_lines = []
    in_table = False

    for line in lines:
        # Check if line looks like a table row (starts with | or contains | surrounded by content)
        is_table_line = bool(re.match(r'^\s*\|.*\|\s*$', line)) or bool(re.match(r'^\s*\|?\s*:?-+:?\s*\|', line))

        if is_table_line:
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
        else:
            if in_table:
                # End of table - wrap collected lines in code block
                if table_lines:
                    result.append('```')
                    result.extend(table_lines)
                    result.append('```')
                table_lines = []
                in_table = False
            result.append(line)

    # Handle table at end of text
    if in_table and table_lines:
        result.append('```')
        result.extend(table_lines)
        result.append('```')

    return '\n'.join(result)


def convert_markdown_for_telegram(text: str) -> tuple[str, str]:
    """
    Convert standard Markdown to Telegram-compatible MarkdownV2.

    Handles tables specially by wrapping them in code blocks since
    Telegram doesn't support table formatting natively.

    Returns:
        tuple: (converted_text, parse_mode) where parse_mode is "MarkdownV2" or None
    """
    # Pre-process: convert tables to code blocks
    text = convert_tables_to_code_blocks(text)

    if not HAS_TELEGRAMIFY:
        # Fallback: return as-is with standard Markdown
        return text, "Markdown"

    try:
        # Convert using telegramify-markdown
        converted = telegramify_markdown.markdownify(text)
        return converted, "MarkdownV2"
    except Exception as e:
        logger.warning(f"telegramify-markdown conversion failed: {e}")
        return text, "Markdown"


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

    # Create new chat if needed (now async)
    backend = BackendService()
    try:
        if not chat_id:
            chat_id = await backend.create_chat(title=prompt[:50])
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

        # Get selected model
        model = context.user_data.get("model", DEFAULT_MODEL)

        response_text, tools, ask_user_options = await backend.send_message(
            chat_id=chat_id,
            message=prompt,
            images=images,
            on_tool_call=on_tool,
            model=model
        )

        # Clear pending images
        context.user_data["pending_images"] = []

        # Store ask_user options for callback handling
        if ask_user_options:
            context.user_data["ask_user_options"] = ask_user_options.options
        else:
            context.user_data.pop("ask_user_options", None)

        # Update chat title if it was generic
        if prompt:
            await backend.update_chat_title(chat_id, prompt[:50])

        # Send response
        await send_ai_response(processing_msg, response_text, chat_id, tools, ask_user_options)
    finally:
        await backend.close()


async def handle_follow_up(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle follow-up message in current chat."""
    message = update.message
    chat_id = context.user_data.get("current_chat_id")

    if not chat_id:
        await message.reply_text("No hay chat activo. Envía una foto para comenzar.")
        return

    # Send processing message
    processing_msg = await message.reply_text("⏳ Procesando...")

    # Send to backend (now async)
    backend = BackendService()
    tools_used = []

    try:
        async def on_tool(tool_display: str):
            tools_used.append(tool_display)
            try:
                await processing_msg.edit_text(f"⏳ Procesando...\n\n{tool_display}")
            except Exception:
                pass

        # Get selected model
        model = context.user_data.get("model", DEFAULT_MODEL)

        response_text, tools, ask_user_options = await backend.send_message(
            chat_id=chat_id,
            message=text,
            images=None,
            on_tool_call=on_tool,
            model=model
        )

        # Store ask_user options for callback handling
        if ask_user_options:
            context.user_data["ask_user_options"] = ask_user_options.options
        else:
            context.user_data.pop("ask_user_options", None)

        # Send response
        await send_ai_response(processing_msg, response_text, chat_id, tools, ask_user_options)
    finally:
        await backend.close()


async def handle_new_text_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle text message that starts a new chat (no images)."""
    message = update.message

    # Create new chat (now async)
    backend = BackendService()

    try:
        chat_id = await backend.create_chat(title=text[:50])

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

        # Get selected model
        model = context.user_data.get("model", DEFAULT_MODEL)

        response_text, tools, ask_user_options = await backend.send_message(
            chat_id=chat_id,
            message=text,
            images=None,
            on_tool_call=on_tool,
            model=model
        )

        # Store ask_user options for callback handling
        if ask_user_options:
            context.user_data["ask_user_options"] = ask_user_options.options
        else:
            context.user_data.pop("ask_user_options", None)

        # Send response
        await send_ai_response(processing_msg, response_text, chat_id, tools, ask_user_options)
    finally:
        await backend.close()


async def send_ai_response(
    processing_msg,
    response_text: str,
    chat_id: str,
    tools: list,
    ask_user_options: AskUserOptions = None
) -> None:
    """Send AI response with chat URL and post-response options.

    If ask_user_options is provided, shows those options as buttons instead of the standard keyboard.
    """
    # Build chat URL
    chat_url = build_chat_url(chat_id)

    # Truncate response if too long (Telegram limit is 4096)
    max_len = 3500  # Leave room for URL and formatting
    if len(response_text) > max_len:
        response_text = response_text[:max_len] + "...\n\n_(Respuesta truncada)_"

    # Format tools used (plain text, will be converted along with response)
    tools_text = ""
    if tools:
        tools_text = "\n\n🔧 **Herramientas usadas:**\n" + "\n".join(f"  • {t}" for t in tools[:5])

    # Build full message with standard Markdown
    full_text = (
        f"{response_text}"
        f"{tools_text}\n\n"
        f"🔗 **Ver en web:**\n{chat_url}"
    )

    # Convert to Telegram-compatible format
    converted_text, parse_mode = convert_markdown_for_telegram(full_text)

    # Use ask_user keyboard if options are provided, otherwise standard keyboard
    if ask_user_options and ask_user_options.options:
        keyboard = build_ask_user_keyboard(ask_user_options.options)
    else:
        keyboard = build_post_response_keyboard()

    # Try with converted markdown
    try:
        await processing_msg.edit_text(
            text=converted_text,
            reply_markup=keyboard,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
        return
    except Exception as e:
        logger.warning(f"Failed to edit with {parse_mode}: {e}")

    # Fallback: try plain Markdown
    try:
        await processing_msg.edit_text(
            text=full_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return
    except Exception as e:
        logger.warning(f"Markdown also failed: {e}")

    # Final fallback: plain text (no formatting)
    plain_tools = ""
    if tools:
        plain_tools = "\n\n🔧 Herramientas usadas:\n" + "\n".join(f"  • {t}" for t in tools[:5])
    plain_text = f"{response_text}{plain_tools}\n\n🔗 Ver en web:\n{chat_url}"

    try:
        await processing_msg.edit_text(
            text=plain_text,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Even plain text edit failed: {e}")
        # Last resort: reply instead of edit
        await processing_msg.reply_text(
            text=plain_text,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
