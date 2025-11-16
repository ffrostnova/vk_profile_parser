"""Вспомогательные функции"""
import logging

logger = logging.getLogger(__name__)


def get_dynamic_delay_for_city(city_name: str) -> tuple:
    """Возвращает динамические задержки для города (универсальные настройки)"""
    # Универсальные задержки для всех городов
    return (5, 8), (3, 6), (2, 4)


def check_user_access(username: str) -> bool:
    """Проверяет, имеет ли пользователь доступ к боту"""
    from config import ALLOWED_USERS
    
    if not username:
        logger.warning(f"Попытка доступа от пользователя без username")
        return False

    clean_username = username.lstrip('@').lower()
    access_granted = clean_username in [user.lower() for user in ALLOWED_USERS]

    if access_granted:
        logger.info(f"Доступ разрешен для пользователя: {username}")
    else:
        logger.warning(f"Доступ запрещен для пользователя: {username}")

    return access_granted

