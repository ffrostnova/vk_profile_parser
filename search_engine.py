"""Движок поиска пользователей"""
import time
import random
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from vk_api.exceptions import ApiError
from config import (
    DELAY_BETWEEN_WALL_CHECKS, DELAY_BETWEEN_USERS, DELAY_AFTER_RATE_LIMIT,
    DELAY_AFTER_FLOOD_CONTROL, DELAY_BETWEEN_CITIES, DELAY_BETWEEN_AGES,
    MIN_USERS_IN_CITY
)
from utils import get_dynamic_delay_for_city
from vk_api_manager import VKAPIManager
from storage import Storage

logger = logging.getLogger(__name__)


class SearchEngine:
    """Класс для поиска пользователей ВКонтакте"""
    
    def __init__(self, vk_manager: VKAPIManager, storage: Storage):
        self.vk_manager = vk_manager
        self.storage = storage
    
    def check_wall_posts(self, user_id: int, keywords_lower: List[str]) -> List[Dict]:
        """Проверяет стену пользователя на наличие ключевых слов"""
        time.sleep(random.uniform(DELAY_BETWEEN_WALL_CHECKS[0], DELAY_BETWEEN_WALL_CHECKS[1]))

        max_retries = self.vk_manager.sessions_count
        current_attempt = 0

        while current_attempt < max_retries:
            vk, token_index = self.vk_manager.get_next_api()
            if not vk:
                break

            try:
                logger.debug(f"Проверка стены пользователя {user_id}")
                wall_posts = vk.wall.get(owner_id=user_id, count=3, filter='owner')
                posts = wall_posts.get('items', [])
                found_matches = []

                for post in posts:
                    post_text = post.get('text', '')
                    if post_text:
                        post_text_lower = post_text.lower()
                        for keyword in keywords_lower:
                            if keyword in post_text_lower:
                                found_matches.append({
                                    'keyword': keyword,
                                    'field': 'стена',
                                    'text': post_text[:200] + '...' if len(post_text) > 200 else post_text,
                                })
                                logger.debug(f"Найдено совпадение в стене: {keyword}")

                if found_matches:
                    logger.info(f"Найдено совпадений в стене пользователя {user_id}: {len(found_matches)}")

                return found_matches

            except ApiError as e:
                current_attempt += 1
                self.vk_manager.mark_token_error(token_index, e.code)
                if e.code == 6 or e.code == 9:
                    logger.warning(f"Ошибка VK API при проверке стены: {e}. Попытка {current_attempt}/{max_retries}")
                    time.sleep(DELAY_AFTER_RATE_LIMIT)
                else:
                    logger.error(f"Ошибка VK API при проверке стены пользователя {user_id}: {e}")
                    break
            except Exception as e:
                logger.debug(f"Ошибка при проверке стены пользователя {user_id}: {e}")
                break

        return []
    
    def search_users_in_city(
        self,
        city_id: int,
        city_name: str,
        keywords: List[str],
        user_settings: Dict,
        offset: int = 0,
        count: int = 50,
        strategy: str = "female"
    ) -> Dict:
        """Ищет пользователей в указанном городе с улучшенной обработкой ошибок"""
        delays = get_dynamic_delay_for_city(city_name)
        request_delay, wall_delay, user_delay = delays

        time.sleep(random.uniform(request_delay[0], request_delay[1]))

        max_retries = self.vk_manager.sessions_count
        current_attempt = 0

        while current_attempt < max_retries:
            vk, token_index = self.vk_manager.get_next_api()
            if not vk:
                return {
                    'found_users': [],
                    'error': 'Нет доступных VK токенов',
                    'users_checked': 0,
                    'total_users': 0,
                    'has_more': False
                }

            try:
                search_params = {
                    'city': city_id,
                    'offset': offset,
                    'count': min(count, 50),
                    'fields': 'city,country,about,activities,interests,music,movies,tv,books,games,quotes,status,photo_200,photo_max_orig,bdate',
                    'has_photo': 1,
                }

                age_from = user_settings.get('age_from')
                age_to = user_settings.get('age_to')

                if age_from and age_to:
                    search_params['age_from'] = age_from
                    search_params['age_to'] = age_to

                if strategy == "female":
                    search_params['sex'] = 1
                elif strategy == "male":
                    search_params['sex'] = 2

                search_params['sort'] = 1

                logger.info(
                    f"Поиск пользователей: город={city_name}, возраст={age_from}-{age_to}, стратегия={strategy}, offset={offset}")

                result = vk.users.search(**search_params)
                total_count = result.get('count', 0)
                users = result.get('items', [])

                logger.info(f"Найдено пользователей в базе: {total_count}, получено: {len(users)}")

                if total_count < MIN_USERS_IN_CITY:
                    logger.info(f"Пропускаем город {city_name}: мало пользователей ({total_count})")
                    return {
                        'found_users': [],
                        'error': f'Мало пользователей: {total_count}',
                        'users_checked': 0,
                        'total_users': total_count,
                        'has_more': False
                    }

                if not users:
                    logger.info(
                        f"Нет пользователей для города {city_name} с параметрами: возраст {age_from}-{age_to}, стратегия {strategy}")
                    return {
                        'found_users': [],
                        'error': None,
                        'users_checked': 0,
                        'total_users': total_count,
                        'has_more': False
                    }

                keywords_lower = [kw.lower() for kw in keywords]
                users_checked = 0
                users_with_matches = 0
                found_users = []

                for user in users:
                    if user.get('is_closed', False):
                        logger.debug(f"Пропуск закрытого профиля: {user.get('first_name')} {user.get('last_name')}")
                        continue

                    if not user.get('photo_200') and not user.get('photo_max_orig'):
                        logger.debug(f"Пропуск пользователя без фото: {user.get('first_name')} {user.get('last_name')}")
                        continue

                    users_checked += 1

                    fields_to_check = {
                        'status': user.get('status', ''),
                        'о себе': user.get('about', ''),
                        'деятельность': user.get('activities', ''),
                        'интересы': user.get('interests', ''),
                        'музыка': user.get('music', ''),
                        'фильмы': user.get('movies', ''),
                        'телешоу': user.get('tv', ''),
                        'книги': user.get('books', ''),
                        'игры': user.get('games', ''),
                        'цитаты': user.get('quotes', '')
                    }

                    found_matches = []
                    for field_name, field_value in fields_to_check.items():
                        if not field_value:
                            continue

                        field_value_lower = str(field_value).lower()
                        for keyword in keywords_lower:
                            if keyword in field_value_lower:
                                found_matches.append({
                                    'keyword': keyword,
                                    'field': field_name,
                                    'text': field_value
                                })
                                logger.debug(f"Найдено совпадение: {keyword} в поле {field_name}")

                    if user_settings.get('check_wall', False):
                        time.sleep(random.uniform(wall_delay[0], wall_delay[1]))
                        wall_matches = self.check_wall_posts(user['id'], keywords_lower)
                        found_matches.extend(wall_matches)

                    if found_matches:
                        users_with_matches += 1
                        user_info = {
                            'id': user['id'],
                            'name': f"{user.get('first_name', '')} {user.get('last_name', '')}",
                            'profile_url': f"https://vk.com/id{user['id']}",
                            'city_id': city_id,
                            'city_name': city_name,
                            'photo_url': user.get('photo_max_orig') or user.get('photo_200') or None,
                            'bdate': user.get('bdate', 'не указана'),
                            'matches': found_matches
                        }
                        found_users.append(user_info)
                        logger.info(
                            f"Найден пользователь с совпадениями: {user_info['name']}, совпадений: {len(found_matches)}")

                logger.info(f"Проверено пользователей: {users_checked}, найдено с совпадениями: {users_with_matches}")

                has_more = (offset + len(users)) < total_count and (offset + len(users)) < 1000

                return {
                    'found_users': found_users,
                    'error': None,
                    'users_checked': users_checked,
                    'total_users': total_count,
                    'has_more': has_more,
                    'offset': offset,
                    'processed_count': offset + len(users),
                    'strategy': strategy
                }

            except ApiError as e:
                current_attempt += 1
                self.vk_manager.mark_token_error(token_index, e.code)
                if e.code == 6 or e.code == 9:
                    logger.warning(f"Ошибка VK API: {e}. Попытка {current_attempt}/{max_retries}")
                    time.sleep(DELAY_AFTER_FLOOD_CONTROL)
                else:
                    logger.error(f'Ошибка VK API при поиске: {e}')
                    return {
                        'found_users': [],
                        'error': f'Ошибка VK API: {e}',
                        'users_checked': 0,
                        'total_users': 0,
                        'has_more': False
                    }
            except Exception as e:
                logger.error(f'Неожиданная ошибка при поиске: {e}')
                return {
                    'found_users': [],
                    'error': f'Неожиданная ошибка: {e}',
                    'users_checked': 0,
                    'total_users': 0,
                    'has_more': False
                }

        return {
            'found_users': [],
            'error': 'Превышено максимальное количество попыток',
            'users_checked': 0,
            'total_users': 0,
            'has_more': False
        }


