"""Inline keyboard builders for Telegram bot."""

from typing import List, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_photo_options_keyboard(recent_chats: List[Tuple[str, str]] = None) -> InlineKeyboardMarkup:
    """Build keyboard for photo options.

    Args:
        recent_chats: List of (chat_id, title) tuples for recent chats
    """
    keyboard = [
        [InlineKeyboardButton("📝 Nuevo chat: Cotizar", callback_data="new:cotizar")],
        [InlineKeyboardButton("📋 Nuevo chat: Pasar datos", callback_data="new:pasar")],
        [InlineKeyboardButton("✏️ Nuevo chat: Escribe el prompt", callback_data="new:custom")],
    ]

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
