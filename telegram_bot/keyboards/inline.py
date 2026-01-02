"""Inline keyboard builders for Telegram bot."""

from typing import List, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_photo_options_keyboard(
    recent_chats: List[Tuple[str, str]] = None,
    caption: str = None
) -> InlineKeyboardMarkup:
    """Build keyboard for photo options.

    Args:
        recent_chats: List of (chat_id, title) tuples for recent chats
        caption: Optional caption text sent with the photo
    """
    keyboard = []

    # If user sent a caption with the image, offer to use it directly
    if caption:
        # Truncate caption for display
        max_display = 25
        display_text = caption[:max_display] + "..." if len(caption) > max_display else caption
        keyboard.append([
            InlineKeyboardButton(f"📨 Nuevo chat: {display_text}", callback_data="new:caption")
        ])

    # Standard options
    keyboard.extend([
        [InlineKeyboardButton("📝 Nuevo chat: Cotizar", callback_data="new:cotizar")],
        [InlineKeyboardButton("📋 Nuevo chat: Pasar datos", callback_data="new:pasar")],
        [InlineKeyboardButton("✏️ Nuevo chat: Escribe el prompt", callback_data="new:custom")],
    ])

    # Add recent chats if available
    if recent_chats:
        keyboard.append([InlineKeyboardButton("─── Continuar en chat ───", callback_data="noop")])
        for chat_id, title in recent_chats[:3]:  # Limit to 3 recent chats
            # Truncate for display and callback data (64 byte limit)
            short_id = chat_id[:10]
            display_title = (title[:22] + "...") if len(title) > 25 else title
            keyboard.append([
                InlineKeyboardButton(f"💬 {display_title}", callback_data=f"cont:{short_id}")
            ])

    return InlineKeyboardMarkup(keyboard)


def build_prompt_selection_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for selecting prompt type after choosing to continue a chat."""
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
    """Build keyboard for selecting from recent chats.

    Args:
        chats: List of (chat_id, title) tuples
    """
    keyboard = []
    for chat_id, title in chats[:5]:  # Limit to 5 chats
        short_id = chat_id[:10]
        display_title = (title[:27] + "...") if len(title) > 30 else title
        keyboard.append([
            InlineKeyboardButton(f"💬 {display_title}", callback_data=f"sel:{short_id}")
        ])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)


def build_confirm_keyboard() -> InlineKeyboardMarkup:
    """Build simple confirm/cancel keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="confirm"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# Available models (must match backend AVAILABLE_MODELS)
AVAILABLE_MODELS = {
    "gemini-3-flash-preview": "🧠 Gemini 3 Flash (razonamiento)",
    "gemini-flash-latest": "⚡ Gemini 2.5 Flash (rápido)",
}
DEFAULT_MODEL = "gemini-3-flash-preview"


def build_model_selection_keyboard(current_model: str = None) -> InlineKeyboardMarkup:
    """Build keyboard for selecting AI model.

    Args:
        current_model: Currently selected model ID
    """
    keyboard = []
    for model_id, display_name in AVAILABLE_MODELS.items():
        # Add checkmark for current model
        if model_id == current_model:
            text = f"✓ {display_name}"
        else:
            text = f"   {display_name}"
        keyboard.append([
            InlineKeyboardButton(text, callback_data=f"model:{model_id}")
        ])
    return InlineKeyboardMarkup(keyboard)


def build_ask_user_keyboard(options: List[str]) -> InlineKeyboardMarkup:
    """Build keyboard for ask_user tool options.

    Args:
        options: List of option strings to display as buttons

    Each option becomes a button that sends the option text as a message.
    Callback data format: askopt:<index>
    """
    keyboard = []
    for idx, option in enumerate(options[:6]):  # Limit to 6 options
        # Truncate for display but keep full text as callback
        display = (option[:35] + "...") if len(option) > 38 else option
        keyboard.append([
            InlineKeyboardButton(display, callback_data=f"askopt:{idx}")
        ])
    return InlineKeyboardMarkup(keyboard)
