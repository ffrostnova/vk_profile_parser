"""Модуль для отправки уведомлений"""
import logging
from typing import Dict
from handlers.keyboard import get_main_keyboard
from storage import Storage

logger = logging.getLogger(__name__)


async def send_user_notification(bot, chat_id: int, user: Dict, search_context: str, storage: Storage) -> None:
    """Отправляет уведомление о найденном пользователе"""
    keyboard = get_main_keyboard()

    if "(" in search_context and ")" in search_context:
        city_part = search_context.split("(")[0].strip()
        age_part = search_context.split("(")[1].replace(")", "").strip()
    else:
        city_part = search_context
        age_part = "возраст не указан"

    storage.save_found_user(user, city_part)
    storage.save_to_excel(user, city_part)

    message = "🚨 Хром работал 24/7 и нашел профиль, необходимо отработать, крепко!\n\n"
    message += "🎯 *НАЙДЕНО СОВПАДЕНИЕ!*\n\n"
    message += f"👤 *{user['name']}*\n"
    message += f"🏙️ Город: {city_part}\n"
    message += f"🎂 Возраст: {age_part}\n"
    message += f"🔗 [Профиль ВК]({user['profile_url']})\n"
    message += f"🎂 День рождения: {user.get('bdate', 'не указан')}\n\n"
    message += "*маркер:*\n"

    for i, match in enumerate(user['matches'][:5]):
        message += f"{i + 1}. *{match['keyword']}* → {match['field']}\n"
        preview = match['text'][:100] + '...' if len(match['text']) > 100 else match['text']
        message += f"   📝 {preview}\n\n"

    if len(user['matches']) > 5:
        message += f"*... и еще {len(user['matches']) - 5} совпадений*\n"

    try:
        if user.get('photo_url'):
            await bot.send_photo(
                chat_id=chat_id,
                photo=user['photo_url'],
                caption=message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        logger.info(f"Отправлено уведомление о пользователе: {user['name']}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        try:
            clean_message = message.replace('*', '').replace('_', '')
            await bot.send_message(chat_id=chat_id, text=clean_message, reply_markup=keyboard)
        except Exception as e2:
            logger.error(f"Ошибка при отправке чистого сообщения: {e2}")

