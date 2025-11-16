"""Декораторы для обработчиков"""
import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from utils import check_user_access

logger = logging.getLogger(__name__)


def access_required(func):
    """Декоратор для проверки доступа к командам"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        username = user.username if user else None

        if not check_user_access(username):
            await update.message.reply_text(
                "❌ Доступ запрещен.\n\n"
                "Бот доступен только для авторизованных пользователей. "
                "Если вы считаете, что это ошибка, свяжитесь с администратором."
            )
            return

        return await func(update, context)

    return wrapper

