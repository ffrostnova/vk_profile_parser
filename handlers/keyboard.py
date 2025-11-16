"""Клавиатуры бота"""
from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создает главную клавиатуру с кнопками"""
    keyboard = [
        [KeyboardButton("📍 Добавить города"), KeyboardButton("🔍 Добавить ключевые слова")],
        [KeyboardButton("🎯 Настройка возраста"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton("🔎 Поиск"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📥 Выгрузить Excel"), KeyboardButton("🗑 Удалить город")],
        [KeyboardButton("🗑️ Удалить ключевые слова"), KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

