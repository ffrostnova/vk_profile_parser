"""Модуль для запуска поиска"""
import asyncio
import random
import logging
from datetime import datetime
from typing import Dict
from config import (
    DELAY_BETWEEN_CITIES, DELAY_BETWEEN_AGES, DELAY_AFTER_FLOOD_CONTROL,
    DELAY_BETWEEN_USERS, MIN_USERS_IN_CITY
)
from vk_api_manager import VKAPIManager
from storage import Storage
from search_engine import SearchEngine
from handlers.keyboard import get_main_keyboard
from handlers.notifications import send_user_notification

logger = logging.getLogger(__name__)


class SearchRunner:
    """Класс для запуска и управления поиском"""
    
    def __init__(self, vk_manager: VKAPIManager, storage: Storage, search_engine: SearchEngine):
        self.vk_manager = vk_manager
        self.storage = storage
        self.search_engine = search_engine
    
    async def run_search(self, application, user_id: int, chat_id: int) -> None:
        """Движок поиска с улучшенной обработкой ошибок и задержками"""
        bot = application.bot
        keyboard = get_main_keyboard()

        user_info = self.storage.get_or_init_user_data(user_id)
        cities = user_info.get('cities', [])
        keywords = user_info.get('keywords', [])
        age_from = user_info.get('age_from', 14)
        age_to = user_info.get('age_to', 35)

        if not cities or not keywords:
            await bot.send_message(chat_id=chat_id, text="❌ Не указаны города или ключевые слова", reply_markup=keyboard)
            return

        search_strategies = ["female", "male"]

        await bot.send_message(
            chat_id=chat_id,
            text=f"🔍 ЗАПУСК ПОИСКА\n"
                 f"🏙️ Городов: {len(cities)}\n"
                 f"🔍 Ключевых слов: {len(keywords)}\n"
                 f"🎯 Возраст: {age_from}-{age_to} лет\n"
                 f"👥 Сначала девушки, потом мужчины\n"
                 f"🔑 Доступно VK токенов: {self.vk_manager.sessions_count}\n\n"
                 f"⏰ Начало: {datetime.now().strftime('%H:%M:%S')}\n\n"
                 f"📊 Бот будет присылать только найденных пользователей",
            reply_markup=keyboard
        )

        logger.info(
            f"Запуск поиска для пользователя {user_id}: города={cities}, ключевые слова={keywords}, возраст={age_from}-{age_to}")

        if user_id in self.storage.search_queue:
            del self.storage.search_queue[user_id]
            self.storage.save_search_queue()

        unique_cities = list(dict.fromkeys(cities))
        city_progress = {}

        for city_name in unique_cities:
            city_id = self.vk_manager.get_city_id(city_name)
            if city_id:
                strategy_progress = {}
                for strategy in search_strategies:
                    age_progress = {}
                    for age in range(age_from, age_to + 1):
                        age_progress[age] = {
                            'offset': 0,
                            'found': 0,
                            'checked': 0,
                            'completed': False
                        }

                    strategy_progress[strategy] = {
                        'age_progress': age_progress,
                        'current_age': age_from,
                        'completed': False
                    }

                city_progress[city_name] = {
                    'id': city_id,
                    'strategies': strategy_progress,
                    'total_found': 0
                }
                logger.info(f"Добавлен город в поиск: {city_name} (ID: {city_id})")
            else:
                logger.warning(f"Не удалось найти ID для города: {city_name}")

        self.storage.search_queue[user_id] = {
            'status': 'searching',
            'cities': list(city_progress.keys()),
            'city_progress': city_progress,
            'current_city_index': 0,
            'current_strategy_index': 0,
            'keywords': keywords,
            'user_settings': user_info,
            'age_range': list(range(age_from, age_to + 1)),
            'started_at': datetime.now().isoformat()
        }
        self.storage.save_search_queue()

        queue_info = self.storage.search_queue[user_id]
        city_progress = queue_info['city_progress']
        cities_list = queue_info['cities']
        user_settings = queue_info.get('user_settings', user_info)

        total_found = 0
        BATCH_SIZE = 50

        logger.info(f"Начало обработки {len(cities_list)} городов")

        for city_index in range(queue_info.get('current_city_index', 0), len(cities_list)):
            city_name = cities_list[city_index]
            progress = city_progress[city_name]
            city_id = progress['id']

            queue_info['current_city_index'] = city_index
            queue_info['current_city'] = city_name
            self.storage.save_search_queue()

            logger.info(f"Обработка города: {city_name} (ID: {city_id})")

            for strategy_index, strategy in enumerate(search_strategies):
                strategy_progress = progress['strategies'][strategy]

                if strategy_progress['completed']:
                    logger.debug(f"Стратегия {strategy} для города {city_name} уже завершена")
                    continue

                queue_info['current_strategy_index'] = strategy_index
                self.storage.save_search_queue()

                current_age = strategy_progress['current_age']
                age_progress = strategy_progress['age_progress'][current_age]

                logger.info(f"Обработка стратегии {strategy}, возраст {current_age} для города {city_name}")

                while current_age <= age_to:
                    if user_id not in self.storage.search_queue or self.storage.search_queue[user_id].get('status') != 'searching':
                        logger.info(f"Поиск прерван для пользователя {user_id}")
                        return

                    if age_progress['completed']:
                        current_age += 1
                        if current_age <= age_to:
                            age_progress = strategy_progress['age_progress'][current_age]
                            strategy_progress['current_age'] = current_age
                            self.storage.save_search_queue()
                        continue

                    while not age_progress['completed']:
                        current_offset = age_progress['offset']

                        if user_id not in self.storage.search_queue or self.storage.search_queue[user_id].get('status') != 'searching':
                            return

                        try:
                            age_specific_settings = user_settings.copy()
                            age_specific_settings['age_from'] = current_age
                            age_specific_settings['age_to'] = current_age

                            logger.info(
                                f"Запрос к VK API: город={city_name}, возраст={current_age}, стратегия={strategy}, offset={current_offset}")

                            result = self.search_engine.search_users_in_city(
                                city_id, city_name, keywords, age_specific_settings,
                                offset=current_offset,
                                count=BATCH_SIZE,
                                strategy=strategy
                            )

                            found_users = result.get('found_users', [])
                            error = result.get('error')
                            processed_count = result.get('processed_count', 0)
                            has_more = result.get('has_more', False)

                            if error:
                                logger.error(f"Ошибка при поиске: {error}")
                                if "Flood control" in error or "[9]" in error:
                                    await bot.send_message(
                                        chat_id=chat_id,
                                        text=f"⏸ Flood control! Ожидание {DELAY_AFTER_FLOOD_CONTROL} секунд...",
                                        reply_markup=keyboard
                                    )
                                    await asyncio.sleep(DELAY_AFTER_FLOOD_CONTROL)
                                    continue
                                elif "Мало пользователей" in error:
                                    logger.info(f"Пропускаем город {city_name} из-за малого количества пользователей")
                                    age_progress['completed'] = True
                                    strategy_progress['completed'] = True
                                    break
                                else:
                                    logger.error(f"Ошибка поиска: {error}")
                                break

                            age_progress['found'] += len(found_users)
                            age_progress['checked'] += result.get('users_checked', 0)
                            age_progress['offset'] = processed_count
                            progress['total_found'] += len(found_users)

                            logger.info(
                                f"Результат поиска: проверено={result.get('users_checked', 0)}, найдено={len(found_users)}, всего в базе={result.get('total_users', 0)}")

                            for user in found_users:
                                await send_user_notification(bot, chat_id, user, f"{city_name} ({current_age} лет)", self.storage)
                                total_found += 1
                                await asyncio.sleep(random.uniform(DELAY_BETWEEN_USERS[0], DELAY_BETWEEN_USERS[1]))

                            if not has_more or processed_count >= 500:
                                age_progress['completed'] = True
                                logger.info(f"Завершен поиск для возраста {current_age} в городе {city_name}")

                            if has_more and not age_progress['completed']:
                                await asyncio.sleep(random.uniform(5, 10))

                        except Exception as e:
                            logger.error(f"Исключение при поиске: {e}")
                            break

                    current_age += 1
                    if current_age <= age_to:
                        strategy_progress['current_age'] = current_age
                        age_progress = strategy_progress['age_progress'][current_age]
                        self.storage.save_search_queue()
                        logger.info(f"Переход к возрасту {current_age} для города {city_name}")
                        await asyncio.sleep(DELAY_BETWEEN_AGES)
                    else:
                        strategy_progress['completed'] = True
                        logger.info(f"Завершена стратегия {strategy} для города {city_name}")
                        break

                await asyncio.sleep(DELAY_BETWEEN_CITIES)

            await asyncio.sleep(DELAY_BETWEEN_CITIES * 2)

        if user_id in self.storage.search_queue:
            self.storage.search_queue[user_id]['status'] = 'completed'
            self.storage.save_search_queue()

        logger.info(f"Поиск завершен для пользователя {user_id}. Всего найдено: {total_found}")
        await bot.send_message(
            chat_id=chat_id,
            text=f"✅ ПОИСК ЗАВЕРШЕН\n\n"
                 f"📊 Всего найдено пользователей: {total_found}\n"
                 f"🏙️ Обработано городов: {len(cities_list)}\n"
                 f"🎂 Обработано возрастов: {age_to - age_from + 1}\n"
                 f"🔑 Использовано VK токенов: {self.vk_manager.sessions_count}\n\n"
                 f"💾 Все данные сохранены в Excel файл",
            reply_markup=keyboard
        )


