"""Command handlers for Telegram bot."""

import logging
import subprocess
import sys
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

from ..keyboards import (
    build_chat_selection_keyboard,
    build_model_selection_keyboard,
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
)
from ..services import BackendService

logger = logging.getLogger(__name__)

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user

    # Set default model if not set
    if "model" not in context.user_data:
        context.user_data["model"] = DEFAULT_MODEL

    await update.message.reply_text(
        f"¡Hola {user.first_name}! 👋\n\n"
        "Soy el bot de Lab Assistant. Puedo ayudarte a:\n\n"
        "📸 **Envía una foto** de un cuaderno o documento para:\n"
        "   • Crear cotizaciones\n"
        "   • Pasar datos al sistema\n"
        "   • Hacer consultas con imágenes\n\n"
        "📝 **Comandos disponibles:**\n"
        "   /chats - Ver chats recientes\n"
        "   /new - Crear nuevo chat\n"
        "   /model - Cambiar modelo de IA\n"
        "   /actualizar - Buscar actualizaciones\n"
        "   /help - Mostrar ayuda\n"
        "   /cancel - Cancelar operación actual\n\n"
        "¡Envía una foto para comenzar!",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    current_model = context.user_data.get("model", DEFAULT_MODEL)
    model_name = AVAILABLE_MODELS.get(current_model, current_model)

    await update.message.reply_text(
        "📚 **Ayuda de Lab Assistant Bot**\n\n"
        "**Cómo usar:**\n"
        "1️⃣ Envía una o varias fotos\n"
        "2️⃣ Selecciona qué quieres hacer:\n"
        "   • Cotizar\n"
        "   • Pasar datos\n"
        "   • Escribir prompt personalizado\n"
        "3️⃣ O continúa en un chat existente\n\n"
        "**Comandos:**\n"
        "/start - Iniciar bot\n"
        "/chats - Ver chats recientes\n"
        "/new - Crear nuevo chat\n"
        "/model - Cambiar modelo de IA\n"
        "/actualizar - Buscar actualizaciones\n"
        "/cancel - Cancelar operación\n"
        "/help - Esta ayuda\n\n"
        f"**Modelo actual:** {model_name}\n\n"
        "**Notas:**\n"
        "• Puedes enviar varias fotos a la vez (álbum)\n"
        "• Al terminar, recibirás un enlace al chat web\n"
        "• Los chats se comparten con la app web",
        parse_mode="Markdown"
    )


async def chats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /chats command - show recent chats."""
    backend = BackendService()
    try:
        chats = await backend.get_recent_chats(limit=5)
    finally:
        await backend.close()

    if not chats:
        await update.message.reply_text(
            "No hay chats recientes.\n\n"
            "Envía una foto para crear uno nuevo."
        )
        return

    keyboard = build_chat_selection_keyboard(chats)
    await update.message.reply_text(
        "📂 **Chats recientes:**\n\n"
        "Selecciona un chat para continuar:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command - create new chat."""
    # Clear any pending state
    context.user_data.clear()

    await update.message.reply_text(
        "➕ **Nuevo chat**\n\n"
        "Envía una foto o escribe tu mensaje para comenzar.",
        parse_mode="Markdown"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command."""
    # Clear user state
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Operación cancelada.\n\n"
        "Envía una foto o usa /help para ver opciones."
    )


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /model command - show model selection."""
    current_model = context.user_data.get("model", DEFAULT_MODEL)
    current_name = AVAILABLE_MODELS.get(current_model, current_model)

    keyboard = build_model_selection_keyboard(current_model)
    await update.message.reply_text(
        f"🤖 **Seleccionar modelo de IA**\n\n"
        f"Modelo actual: {current_name}\n\n"
        "Selecciona un modelo:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /actualizar command - check for and apply updates."""
    await update.message.reply_text("🔄 Verificando actualizaciones...")

    try:
        # Fetch latest from origin
        fetch_result = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )

        if fetch_result.returncode != 0:
            await update.message.reply_text(
                "❌ Error al verificar actualizaciones:\n"
                f"`{fetch_result.stderr}`",
                parse_mode="Markdown"
            )
            return

        # Check if we're behind origin
        status_result = subprocess.run(
            ["git", "status", "-uno"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )

        if "Your branch is behind" in status_result.stdout:
            # Get commit count
            count_result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..origin/HEAD"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=10
            )
            commit_count = count_result.stdout.strip() or "?"

            await update.message.reply_text(
                f"📦 Hay {commit_count} actualización(es) disponible(s).\n\n"
                "Aplicando actualizaciones..."
            )

            # Pull updates
            pull_result = subprocess.run(
                ["git", "pull", "origin"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60
            )

            if pull_result.returncode != 0:
                await update.message.reply_text(
                    "❌ Error al aplicar actualizaciones:\n"
                    f"`{pull_result.stderr}`",
                    parse_mode="Markdown"
                )
                return

            # Get last commit info
            log_result = subprocess.run(
                ["git", "log", "-1", "--format=%s"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=10
            )
            last_commit = log_result.stdout.strip()

            await update.message.reply_text(
                "✅ **Actualización completada**\n\n"
                f"Último cambio: {last_commit}\n\n"
                "🔄 Reiniciando servicios...\n"
                "El bot volverá en unos segundos.",
                parse_mode="Markdown"
            )

            # Restart by starting Lab_Assistant.bat with --restart flag
            # This will restart all services including this bot
            bat_path = PROJECT_ROOT / "Lab_Assistant.bat"
            if bat_path.exists():
                subprocess.Popen(
                    ["cmd", "/c", str(bat_path), "--restart"],
                    cwd=PROJECT_ROOT,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
                )
                # Exit this bot instance
                import os
                os._exit(0)
            else:
                await update.message.reply_text(
                    "⚠️ No se pudo reiniciar automáticamente.\n"
                    "Por favor reinicia Lab_Assistant.bat manualmente."
                )

        elif "Your branch is up to date" in status_result.stdout:
            await update.message.reply_text(
                "✅ La aplicación está actualizada.\n\n"
                "No hay nuevas actualizaciones disponibles."
            )
        else:
            # Unknown state, show status
            await update.message.reply_text(
                f"ℹ️ Estado actual:\n`{status_result.stdout[:500]}`",
                parse_mode="Markdown"
            )

    except subprocess.TimeoutExpired:
        await update.message.reply_text("❌ Tiempo de espera agotado. Intenta de nuevo.")
    except Exception as e:
        logger.error(f"Update command error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
