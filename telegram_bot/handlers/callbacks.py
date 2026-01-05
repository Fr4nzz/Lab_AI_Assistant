"""Callback query handlers for inline keyboard buttons."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..keyboards import (
    build_prompt_selection_keyboard,
    build_post_response_keyboard,
    build_chat_selection_keyboard,
    build_photo_options_keyboard,
    build_model_selection_keyboard,
    build_ask_user_keyboard,
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
)
from ..services import BackendService, AskUserOptions
from ..utils import build_chat_url

logger = logging.getLogger(__name__)

# Predefined prompts
PROMPTS = {
    "cotizar": "Cotiza",
    "pasar": "Pasa o revisa que esten bien pasados los datos de estos pacientes",
}


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()  # Always acknowledge

    data = query.data
    logger.info(f"Callback received: {data}")

    # Route to appropriate handler
    if data == "noop":
        return  # Separator button, do nothing

    elif data == "cancel":
        await handle_cancel(query, context)

    elif data.startswith("new:"):
        await handle_new_chat(query, context, data[4:])

    elif data.startswith("cont:"):
        await handle_continue_chat(query, context, data[5:])

    elif data.startswith("prompt:"):
        await handle_prompt_selection(query, context, data[7:])

    elif data.startswith("post:"):
        await handle_post_response(query, context, data[5:])

    elif data.startswith("sel:"):
        await handle_chat_selection(query, context, data[4:])

    elif data.startswith("model:"):
        await handle_model_selection(query, context, data[6:])

    elif data.startswith("askopt:"):
        await handle_ask_user_option(query, context, data[7:])

    elif data.startswith("audio:"):
        await handle_audio_action(query, context, data[6:])


async def handle_cancel(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancel button."""
    context.user_data.clear()
    await query.edit_message_text("❌ Operación cancelada.")


async def handle_new_chat(query, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """Handle 'new chat' buttons (cotizar, pasar, caption, custom)."""
    # Use original images - rotation is handled by backend's image-rotation tool
    images = context.user_data.get("pending_images", [])

    if action == "custom":
        # Wait for user to type custom prompt
        context.user_data["awaiting_prompt"] = True
        context.user_data["pending_chat_id"] = None
        await query.message.reply_text(
            "✏️ Escribe el prompt para acompañar la(s) imagen(es):"
        )
        return

    # Handle "caption" action - use the caption the user sent with the image
    if action == "caption":
        caption = context.user_data.get("pending_caption")
        if not caption:
            await query.message.reply_text("❌ No hay mensaje guardado. Usa otra opción.")
            return
        prompt = caption
        # Use first part of caption as title (up to 50 chars)
        title = caption[:50] if len(caption) <= 50 else caption[:47] + "..."
    else:
        # Get predefined prompt
        prompt = PROMPTS.get(action, f"Analiza esta imagen: {action}")
        title = "Cotización" if action == "cotizar" else "Pasar datos" if action == "pasar" else action

    # Create new chat (now async)
    backend = BackendService()

    try:
        chat_id = await backend.create_chat(title=title)

        if not chat_id:
            await query.message.reply_text("❌ Error al crear el chat.")
            return

        context.user_data["current_chat_id"] = chat_id
        context.user_data["pending_images"] = []
        context.user_data["pending_caption"] = None  # Clear caption after use

        # Show processing message
        await query.message.reply_text("⏳ Procesando...")

        # Send to backend (send new message for each tool)
        tools_used = []

        async def on_tool(tool_display: str):
            tools_used.append(tool_display)
            try:
                await query.message.reply_text(tool_display)
            except Exception:
                pass

        # Get selected model (default to gemini-3-flash-preview)
        model = context.user_data.get("model", DEFAULT_MODEL)

        response_text, tools, ask_user_options = await backend.send_message(
            chat_id=chat_id,
            message=prompt,
            images=images,
            on_tool_call=on_tool,
            model=model
        )

        # Store ask_user options for callback handling
        if ask_user_options:
            context.user_data["ask_user_options"] = ask_user_options.options
        else:
            context.user_data.pop("ask_user_options", None)

        # Send response as new message
        await send_response(query, context, response_text, chat_id, tools, ask_user_options)
    finally:
        await backend.close()


async def handle_continue_chat(query, context: ContextTypes.DEFAULT_TYPE, short_id: str) -> None:
    """Handle 'continue in chat' buttons."""
    backend = BackendService()
    try:
        chat_info = await backend.get_chat_by_short_id(short_id)

        if not chat_info:
            await query.edit_message_text("❌ Chat no encontrado.")
            return

        full_chat_id, title = chat_info
        context.user_data["pending_chat_id"] = full_chat_id

        # Show prompt selection
        keyboard = build_prompt_selection_keyboard()
        await query.edit_message_text(
            f"💬 Continuar en: *{title}*\n\n"
            "Selecciona qué hacer con la(s) imagen(es):",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    finally:
        await backend.close()


async def handle_prompt_selection(query, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """Handle prompt selection after choosing to continue a chat."""
    # Use original images - rotation is handled by backend's image-rotation tool
    images = context.user_data.get("pending_images", [])
    chat_id = context.user_data.get("pending_chat_id")

    if not chat_id:
        await query.message.reply_text("❌ No hay chat seleccionado.")
        return

    if action == "custom":
        context.user_data["awaiting_prompt"] = True
        await query.message.reply_text(
            "✏️ Escribe el prompt para acompañar la(s) imagen(es):"
        )
        return

    # Get predefined prompt
    prompt = PROMPTS.get(action, f"Analiza esta imagen: {action}")

    context.user_data["current_chat_id"] = chat_id
    context.user_data["pending_images"] = []

    # Show processing message
    await query.message.reply_text("⏳ Procesando...")

    # Send to backend (send new message for each tool)
    backend = BackendService()
    tools_used = []

    try:
        async def on_tool(tool_display: str):
            tools_used.append(tool_display)
            try:
                await query.message.reply_text(tool_display)
            except Exception:
                pass

        # Get selected model (default to gemini-3-flash-preview)
        model = context.user_data.get("model", DEFAULT_MODEL)

        response_text, tools, ask_user_options = await backend.send_message(
            chat_id=chat_id,
            message=prompt,
            images=images,
            on_tool_call=on_tool,
            model=model
        )

        # Store ask_user options for callback handling
        if ask_user_options:
            context.user_data["ask_user_options"] = ask_user_options.options
        else:
            context.user_data.pop("ask_user_options", None)

        # Send response as new message
        await send_response(query, context, response_text, chat_id, tools, ask_user_options)
    finally:
        await backend.close()


async def handle_post_response(query, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """Handle post-response buttons (follow, new, select)."""
    if action == "follow":
        # Keep current chat, ready for follow-up
        chat_id = context.user_data.get("current_chat_id")
        if chat_id:
            await query.edit_message_text(
                query.message.text + "\n\n💬 _Escribe tu mensaje de seguimiento..._",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        else:
            await query.edit_message_text("No hay chat activo. Envía una foto para comenzar.")

    elif action == "new":
        # Clear state for new chat
        context.user_data.clear()
        await query.edit_message_text(
            query.message.text + "\n\n➕ _Envía una foto para crear un nuevo chat_",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    elif action == "select":
        # Show chat selection (now async)
        backend = BackendService()
        try:
            chats = await backend.get_recent_chats(limit=5)
        finally:
            await backend.close()

        if not chats:
            await query.edit_message_text("No hay chats disponibles.")
            return

        keyboard = build_chat_selection_keyboard(chats)
        await query.edit_message_text(
            "📂 Selecciona un chat:",
            reply_markup=keyboard
        )


async def handle_chat_selection(query, context: ContextTypes.DEFAULT_TYPE, short_id: str) -> None:
    """Handle chat selection from list."""
    backend = BackendService()
    try:
        chat_info = await backend.get_chat_by_short_id(short_id)

        if not chat_info:
            await query.edit_message_text("❌ Chat no encontrado.")
            return

        full_chat_id, title = chat_info
        context.user_data["current_chat_id"] = full_chat_id

        chat_url = build_chat_url(full_chat_id)
        await query.edit_message_text(
            f"💬 Chat seleccionado: *{title}*\n\n"
            f"🔗 {chat_url}\n\n"
            "_Escribe tu mensaje o envía una foto..._",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    finally:
        await backend.close()


async def handle_model_selection(query, context: ContextTypes.DEFAULT_TYPE, model_id: str) -> None:
    """Handle model selection from /model command."""
    if model_id not in AVAILABLE_MODELS:
        await query.edit_message_text(f"❌ Modelo no válido: {model_id}")
        return

    # Save selected model
    context.user_data["model"] = model_id
    model_name = AVAILABLE_MODELS[model_id]

    await query.edit_message_text(
        f"✅ Modelo cambiado a: {model_name}\n\n"
        "_Este modelo se usará para las próximas conversaciones._",
        parse_mode="Markdown"
    )
    logger.info(f"User selected model: {model_id}")


async def handle_ask_user_option(query, context: ContextTypes.DEFAULT_TYPE, option_index: str) -> None:
    """Handle ask_user option button click.

    Sends the selected option text as a follow-up message to the current chat.
    """
    chat_id = context.user_data.get("current_chat_id")
    options = context.user_data.get("ask_user_options", [])

    if not chat_id:
        await query.message.reply_text("❌ No hay chat activo.")
        return

    try:
        idx = int(option_index)
        if idx < 0 or idx >= len(options):
            await query.message.reply_text("❌ Opción no válida.")
            return
        selected_option = options[idx]
    except (ValueError, IndexError):
        await query.message.reply_text("❌ Opción no válida.")
        return

    # Clear the stored options
    context.user_data.pop("ask_user_options", None)

    # Show processing message with selected option
    await query.message.reply_text(f"✅ Seleccionado: {selected_option}")
    await query.message.reply_text("⏳ Procesando...")

    # Send the selected option as a message
    backend = BackendService()
    tools_used = []

    try:
        async def on_tool(tool_display: str):
            tools_used.append(tool_display)
            try:
                await query.message.reply_text(tool_display)
            except Exception:
                pass

        model = context.user_data.get("model", DEFAULT_MODEL)

        response_text, tools, ask_user_options = await backend.send_message(
            chat_id=chat_id,
            message=selected_option,
            images=None,
            on_tool_call=on_tool,
            model=model
        )

        # Store new ask_user options if present
        if ask_user_options:
            context.user_data["ask_user_options"] = ask_user_options.options
        else:
            context.user_data.pop("ask_user_options", None)

        # Send response as new message
        await send_response(query, context, response_text, chat_id, tools, ask_user_options)
    finally:
        await backend.close()


async def handle_audio_action(query, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """Handle audio action buttons.

    Actions:
        new - New chat with audio only
        new_with_images - New chat with audio + pending images
        new_audio_only - New chat with just audio (ignoring pending images)
        custom - Wait for user to type custom prompt
        cont:<short_id> - Continue in existing chat
    """
    audio = context.user_data.get("pending_audio")
    audio_mime = context.user_data.get("pending_audio_mime", "audio/ogg")
    images = context.user_data.get("pending_images", [])

    if not audio:
        await query.message.reply_text("❌ No hay audio guardado. Envía un audio primero.")
        return

    backend = BackendService()

    try:
        if action == "custom":
            # Wait for user to type custom prompt
            context.user_data["awaiting_audio_prompt"] = True
            context.user_data["pending_chat_id"] = None
            await query.message.reply_text(
                "✏️ Escribe el prompt para acompañar el audio:"
            )
            return

        elif action.startswith("cont:"):
            # Continue in existing chat
            short_id = action[5:]
            chat_info = await backend.get_chat_by_short_id(short_id)

            if not chat_info:
                await query.edit_message_text("❌ Chat no encontrado.")
                return

            full_chat_id, title = chat_info
            context.user_data["current_chat_id"] = full_chat_id

            # Determine what to include
            include_images = len(images) > 0
            prompt = "Analiza este audio" if not include_images else "Analiza este audio y las imágenes"

            # Clear pending data
            context.user_data["pending_audio"] = None
            context.user_data["pending_audio_mime"] = None
            if include_images:
                context.user_data["pending_images"] = []

            # Show processing message
            await query.message.reply_text("⏳ Procesando...")

            # Send to backend
            tools_used = []

            async def on_tool(tool_display: str):
                tools_used.append(tool_display)
                try:
                    await query.message.reply_text(tool_display)
                except Exception:
                    pass

            model = context.user_data.get("model", DEFAULT_MODEL)

            response_text, tools, ask_user_options = await backend.send_message(
                chat_id=full_chat_id,
                message=prompt,
                images=images if include_images else None,
                audio=audio,
                audio_mime=audio_mime,
                on_tool_call=on_tool,
                model=model
            )

            if ask_user_options:
                context.user_data["ask_user_options"] = ask_user_options.options
            else:
                context.user_data.pop("ask_user_options", None)

            await send_response(query, context, response_text, full_chat_id, tools, ask_user_options)
            return

        # Handle new chat actions
        if action == "new_with_images":
            # New chat with audio + images
            title = "Audio + Imágenes"
            include_images = True
            prompt = "Analiza este audio junto con las imágenes"
        elif action == "new_audio_only":
            # New chat with just audio (ignore pending images)
            title = "Audio"
            include_images = False
            prompt = "Analiza este audio"
        elif action == "new":
            # New chat with audio (no images pending)
            title = "Audio"
            include_images = False
            prompt = "Analiza este audio"
        else:
            await query.message.reply_text(f"❌ Acción no reconocida: {action}")
            return

        # Create new chat
        chat_id = await backend.create_chat(title=title)

        if not chat_id:
            await query.message.reply_text("❌ Error al crear el chat.")
            return

        context.user_data["current_chat_id"] = chat_id

        # Clear pending data
        context.user_data["pending_audio"] = None
        context.user_data["pending_audio_mime"] = None
        if include_images:
            context.user_data["pending_images"] = []

        # Show processing message
        await query.message.reply_text("⏳ Procesando...")

        # Send to backend
        tools_used = []

        async def on_tool(tool_display: str):
            tools_used.append(tool_display)
            try:
                await query.message.reply_text(tool_display)
            except Exception:
                pass

        model = context.user_data.get("model", DEFAULT_MODEL)

        response_text, tools, ask_user_options = await backend.send_message(
            chat_id=chat_id,
            message=prompt,
            images=images if include_images else None,
            audio=audio,
            audio_mime=audio_mime,
            on_tool_call=on_tool,
            model=model
        )

        if ask_user_options:
            context.user_data["ask_user_options"] = ask_user_options.options
        else:
            context.user_data.pop("ask_user_options", None)

        await send_response(query, context, response_text, chat_id, tools, ask_user_options)

    finally:
        await backend.close()


async def send_response(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    response_text: str,
    chat_id: str,
    tools: list,
    ask_user_options: AskUserOptions = None
) -> None:
    """Send AI response as new message with URL and post-response options.

    If ask_user_options is provided, shows those options as buttons instead of the standard keyboard.
    """
    chat_url = build_chat_url(chat_id)

    # Truncate if needed
    max_len = 3500
    if len(response_text) > max_len:
        response_text = response_text[:max_len] + "...\n\n_(Respuesta truncada)_"

    full_text = (
        f"{response_text}\n\n"
        f"🔗 *Ver en web:*\n{chat_url}"
    )

    # Use ask_user keyboard if options are provided, otherwise standard keyboard
    if ask_user_options and ask_user_options.options:
        keyboard = build_ask_user_keyboard(ask_user_options.options)
    else:
        keyboard = build_post_response_keyboard()

    # Try sending with Markdown, fall back to plain text if parsing fails
    try:
        await query.message.reply_text(
            text=full_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Markdown parsing failed: {e}")
        # Build plain text version without markdown
        plain_text = f"{response_text}\n\n🔗 Ver en web:\n{chat_url}"
        try:
            await query.message.reply_text(
                text=plain_text,
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
        except Exception as e2:
            logger.error(f"Failed to send response: {e2}")
