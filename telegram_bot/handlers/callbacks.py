"""Callback query handlers for inline keyboard buttons."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..keyboards import (
    build_prompt_selection_keyboard,
    build_post_response_keyboard,
    build_chat_selection_keyboard,
    build_photo_options_keyboard,
)
from ..services import BackendService
from ..utils import build_chat_url

logger = logging.getLogger(__name__)

# Predefined prompts
PROMPTS = {
    "cotizar": "Por favor analiza esta imagen y genera una cotización con los exámenes de laboratorio que identificas. Lista cada examen con su código si es posible.",
    "pasar": "Por favor analiza esta imagen y extrae los datos que ves para pasarlos al sistema. Identifica: nombre del paciente, cédula, exámenes solicitados, y cualquier otra información relevante.",
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


async def handle_cancel(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancel button."""
    context.user_data.clear()
    await query.edit_message_text("❌ Operación cancelada.")


async def handle_new_chat(query, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """Handle 'new chat' buttons (cotizar, pasar, custom)."""
    images = context.user_data.get("pending_images", [])

    if action == "custom":
        # Wait for user to type custom prompt
        context.user_data["awaiting_prompt"] = True
        context.user_data["pending_chat_id"] = None
        await query.edit_message_text(
            "✏️ Escribe el prompt para acompañar la(s) imagen(es):"
        )
        return

    # Get predefined prompt
    prompt = PROMPTS.get(action, f"Analiza esta imagen: {action}")

    # Create new chat (now async)
    backend = BackendService()
    title = "Cotización" if action == "cotizar" else "Pasar datos" if action == "pasar" else action

    try:
        chat_id = await backend.create_chat(title=title)

        if not chat_id:
            await query.edit_message_text("❌ Error al crear el chat.")
            return

        context.user_data["current_chat_id"] = chat_id
        context.user_data["pending_images"] = []

        # Show processing message
        await query.edit_message_text("⏳ Procesando...")

        # Send to backend
        tools_used = []

        async def on_tool(tool_display: str):
            tools_used.append(tool_display)
            try:
                await query.edit_message_text(f"⏳ Procesando...\n\n{tool_display}")
            except Exception:
                pass

        response_text, tools = await backend.send_message(
            chat_id=chat_id,
            message=prompt,
            images=images,
            on_tool_call=on_tool
        )

        # Send response
        await send_response(query, response_text, chat_id, tools)
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
    images = context.user_data.get("pending_images", [])
    chat_id = context.user_data.get("pending_chat_id")

    if not chat_id:
        await query.edit_message_text("❌ No hay chat seleccionado.")
        return

    if action == "custom":
        context.user_data["awaiting_prompt"] = True
        await query.edit_message_text(
            "✏️ Escribe el prompt para acompañar la(s) imagen(es):"
        )
        return

    # Get predefined prompt
    prompt = PROMPTS.get(action, f"Analiza esta imagen: {action}")

    context.user_data["current_chat_id"] = chat_id
    context.user_data["pending_images"] = []

    # Show processing message
    await query.edit_message_text("⏳ Procesando...")

    # Send to backend
    backend = BackendService()
    tools_used = []

    try:
        async def on_tool(tool_display: str):
            tools_used.append(tool_display)
            try:
                await query.edit_message_text(f"⏳ Procesando...\n\n{tool_display}")
            except Exception:
                pass

        response_text, tools = await backend.send_message(
            chat_id=chat_id,
            message=prompt,
            images=images,
            on_tool_call=on_tool
        )

        # Send response
        await send_response(query, response_text, chat_id, tools)
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


async def send_response(query, response_text: str, chat_id: str, tools: list) -> None:
    """Send AI response with URL and post-response options."""
    chat_url = build_chat_url(chat_id)

    # Format tools used
    tools_text = ""
    if tools:
        tools_text = "\n\n🔧 *Herramientas usadas:*\n" + "\n".join(f"  • {t}" for t in tools[:5])

    # Truncate if needed
    max_len = 3500
    if len(response_text) > max_len:
        response_text = response_text[:max_len] + "...\n\n_(Respuesta truncada)_"

    full_text = (
        f"{response_text}"
        f"{tools_text}\n\n"
        f"🔗 *Ver en web:*\n{chat_url}"
    )

    keyboard = build_post_response_keyboard()

    try:
        await query.edit_message_text(
            text=full_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")
        # Send as new message if edit fails
        await query.message.reply_text(
            text=full_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
