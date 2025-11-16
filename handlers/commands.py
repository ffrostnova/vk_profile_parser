"""Обработчики команд бота"""
import os
import logging
from datetime import datetime
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes
from handlers.decorators import access_required
from handlers.keyboard import get_main_keyboard
from config import EXCEL_FILE

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Класс с обработчиками команд бота"""
    
    def __init__(self, storage, vk_manager, search_engine, search_runner):
        self.storage = storage
        self.vk_manager = vk_manager
        self.search_engine = search_engine
        self.search_runner = search_runner
    
    @access_required
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /start"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        user_info = self.storage.get_or_init_user_data(user_id)
        keyboard = get_main_keyboard()

        cities_count = len(user_info.get('cities', []))
        keywords_count = len(user_info.get('keywords', []))
        age_from = user_info.get('age_from', 14)
        age_to = user_info.get('age_to', 35)

        welcome_msg = "👋 Бот для поиска пользователей ВКонтакте\n\n"
        welcome_msg += "🎯 *ТЕКУЩИЕ НАСТРОЙКИ:*\n"
        welcome_msg += f"• Возраст: {age_from}-{age_to} лет\n"
        welcome_msg += "• Сначала девушки, потом мужчины\n"
        welcome_msg += "• Только с аватаром\n"
        welcome_msg += "• Открытые профили\n"
        welcome_msg += f"• Доступно VK токенов: {self.vk_manager.sessions_count}\n\n"

        if cities_count > 0 or keywords_count > 0:
            welcome_msg += f"✅ Загружены настройки:\n"
            if cities_count > 0:
                welcome_msg += f"• Города: {cities_count}\n"
            if keywords_count > 0:
                welcome_msg += f"• Ключевые слова: {keywords_count}\n"

        if user_id in self.storage.search_queue and self.storage.search_queue[user_id].get('status') == 'searching':
            welcome_msg += "🔄 Обнаружен активный поиск\n"

        await context.bot.send_message(chat_id=chat_id, text=welcome_msg, reply_markup=keyboard, parse_mode='Markdown')
    
    @access_required
    async def handle_add_cities(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик кнопки '📍 Добавить города'"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        self.storage.user_states[user_id] = 'waiting_for_cities'

        await context.bot.send_message(
            chat_id=chat_id,
            text="📍 Введите названия городов через запятую:",
            reply_markup=get_main_keyboard()
        )
    
    @access_required
    async def handle_add_keywords(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик кнопки '🔍 Добавить ключевые слова'"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        self.storage.user_states[user_id] = 'waiting_for_keywords'

        await context.bot.send_message(
            chat_id=chat_id,
            text="🔍 Введите ключевые слова через запятую:",
            reply_markup=get_main_keyboard()
        )
    
    @access_required
    async def handle_age_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик кнопки '🎯 Настройка возраста'"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        self.storage.user_states[user_id] = 'waiting_for_age'

        await context.bot.send_message(
            chat_id=chat_id,
            text="🎯 Введите возрастной диапазон в формате ОТ-ДО\nПример: 18-25",
            reply_markup=get_main_keyboard()
        )
    
    @access_required
    async def handle_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик кнопки '⚙️ Настройки'"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        user_info = self.storage.get_or_init_user_data(user_id)

        cities = user_info.get('cities', [])
        keywords = user_info.get('keywords', [])
        age_from = user_info.get('age_from', 14)
        age_to = user_info.get('age_to', 35)

        message = "⚙️ Текущие настройки:\n\n"
        message += f"🏙️ Города: {', '.join(cities) if cities else 'не указаны'}\n"
        message += f"🔍 Ключевые слова: {', '.join(keywords) if keywords else 'не указаны'}\n"
        message += f"🎯 Возраст: {age_from}-{age_to} лет\n"
        message += f"🔑 Доступно VK токенов: {self.vk_manager.sessions_count}\n"
        message += "👥 Поиск: сначала девушки, потом мужчины\n"
        message += "🖼️ Только с аватаром\n"
        message += "🔓 Открытые профили"

        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=get_main_keyboard())
    
    @access_required
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик кнопки '🔎 Поиск'"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        if user_id in self.storage.search_queue:
            del self.storage.search_queue[user_id]
            self.storage.save_search_queue()

        await self.search_runner.run_search(context.application, user_id, chat_id)
    
    @access_required
    async def handle_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик кнопки '📊 Статистика'"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        if not os.path.exists(EXCEL_FILE):
            await context.bot.send_message(chat_id=chat_id, text="📊 Файл еще не создан", reply_markup=get_main_keyboard())
            return

        try:
            df = pd.read_excel(EXCEL_FILE)
            total_users = len(df)
            city_stats = df['Город'].value_counts().to_dict()

            stats_message = f"📊 Статистика:\n\n"
            stats_message += f"👤 Всего пользователей: {total_users}\n\n"
            stats_message += f"🏙️ По городам:\n"

            for city, count in list(city_stats.items())[:10]:
                stats_message += f"• {city}: {count}\n"

            if len(city_stats) > 10:
                stats_message += f"• ... и еще {len(city_stats) - 10} городов\n"

            stats_message += f"\n💾 Размер файла: {os.path.getsize(EXCEL_FILE) / 1024:.1f} KB"

            await context.bot.send_message(chat_id=chat_id, text=stats_message, reply_markup=get_main_keyboard())

        except Exception as e:
            logger.error(f"Ошибка при чтении файла статистики: {e}")
            await context.bot.send_message(chat_id=chat_id, text="❌ Ошибка при чтении файла",
                                           reply_markup=get_main_keyboard())
    
    @access_required
    async def handle_download_excel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик кнопки '📥 Выгрузить Excel'"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        if not os.path.exists(EXCEL_FILE):
            await context.bot.send_message(chat_id=chat_id, text="❌ Файл не найден", reply_markup=get_main_keyboard())
            return

        try:
            file_size = os.path.getsize(EXCEL_FILE)

            if file_size == 0:
                await context.bot.send_message(chat_id=chat_id, text="❌ Файл пуст", reply_markup=get_main_keyboard())
                return

            with open(EXCEL_FILE, 'rb') as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=f"найденные_пользователи_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    caption="📊 Excel файл с найденными пользователями",
                    reply_markup=get_main_keyboard()
                )

        except Exception as e:
            logger.error(f"Ошибка при отправке файла: {e}")
            await context.bot.send_message(chat_id=chat_id, text="❌ Ошибка при отправке файла",
                                           reply_markup=get_main_keyboard())
    
    @access_required
    async def handle_delete_city(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик кнопки '🗑 Удалить город'"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        user_info = self.storage.get_or_init_user_data(user_id)

        cities = user_info.get('cities', [])

        if not cities:
            await context.bot.send_message(
                chat_id=chat_id,
                text="ℹ️ У вас нет сохраненных городов для удаления",
                reply_markup=get_main_keyboard()
            )
            return

        self.storage.user_states[user_id] = 'waiting_for_city_to_delete'

        cities_list = "\n".join([f"{i + 1}. {city}" for i, city in enumerate(cities)])
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🗑 Выберите город для удаления (введите номер):\n\n{cities_list}",
            reply_markup=get_main_keyboard()
        )
    
    @access_required
    async def handle_delete_keywords(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик кнопки '🗑️ Удалить ключевые слова'"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        user_info = self.storage.get_or_init_user_data(user_id)

        keywords_count = len(user_info.get('keywords', []))

        if keywords_count == 0:
            await context.bot.send_message(
                chat_id=chat_id,
                text="ℹ️ У вас нет сохраненных ключевых слов для удаления",
                reply_markup=get_main_keyboard()
            )
            return

        user_info['keywords'] = []
        self.storage.save_user_data()

        message = "🗑️ Ключевые слова удалены\n\n"
        message += f"✅ Удалено ключевых слов: {keywords_count}"

        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=get_main_keyboard())
    
    @access_required
    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик кнопки '❓ Помощь'"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        help_text = """
❓ Помощь по боту

Основные функции:
📍 Добавить города - указать города для поиска
🔍 Добавить ключевые слова - указать ключевые слова для поиска
🎯 Настройка возраста - установить возрастной диапазон
🔎 Поиск - начать поиск пользователей
⚙️ Настройки - посмотреть текущие настройки
📊 Статистика - статистика найденных пользователей
📥 Выгрузить Excel - скачать Excel файл с результатами
🗑 Удалить город - удалить конкретный город из списка
🗑️ Удалить ключевые слова - удалить все ключевые слова

Как использовать:
1. Добавьте города
2. Добавьте ключевые слова  
3. Настройте возраст
4. Нажмите Поиск
5. Бот будет присылать найденных пользователей
6. Скачайте результаты через Выгрузить Excel
"""

        await context.bot.send_message(chat_id=chat_id, text=help_text, reply_markup=get_main_keyboard())
    
    @access_required
    async def handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Сброс состояния поиска (для отладки)"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        if user_id in self.storage.search_queue:
            del self.storage.search_queue[user_id]
            self.storage.save_search_queue()

        if user_id in self.storage.user_states:
            del self.storage.user_states[user_id]

        await context.bot.send_message(
            chat_id=chat_id,
            text="🔄 Состояние поиска сброшено",
            reply_markup=get_main_keyboard()
        )
    
    @access_required
    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик текстового ввода"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        text = update.message.text.strip()

        user_info = self.storage.get_or_init_user_data(user_id)

        if user_id in self.storage.user_states:
            state = self.storage.user_states[user_id]

            if state == 'waiting_for_cities':
                cities = [city.strip() for city in text.split(',')]
                user_info['cities'] = cities
                self.storage.save_user_data()
                del self.storage.user_states[user_id]
                await context.bot.send_message(chat_id=chat_id, text=f"✅ Города сохранены",
                                               reply_markup=get_main_keyboard())

            elif state == 'waiting_for_keywords':
                keywords = [keyword.strip() for keyword in text.split(',')]
                user_info['keywords'] = keywords
                self.storage.save_user_data()
                del self.storage.user_states[user_id]
                await context.bot.send_message(chat_id=chat_id, text=f"✅ Ключевые слова сохранены",
                                               reply_markup=get_main_keyboard())

            elif state == 'waiting_for_age':
                try:
                    if '-' in text:
                        age_parts = text.split('-')
                        if len(age_parts) == 2:
                            age_from = int(age_parts[0].strip())
                            age_to = int(age_parts[1].strip())

                            if age_from < 14:
                                await context.bot.send_message(chat_id=chat_id, text="❌ Минимальный возраст: 14 лет",
                                                               reply_markup=get_main_keyboard())
                                return

                            if age_to > 80:
                                await context.bot.send_message(chat_id=chat_id, text="❌ Максимальный возраст: 80 лет",
                                                               reply_markup=get_main_keyboard())
                                return

                            if age_from > age_to:
                                await context.bot.send_message(chat_id=chat_id,
                                                               text="❌ Начальный возраст не может быть больше конечного",
                                                               reply_markup=get_main_keyboard())
                                return

                            user_info['age_from'] = age_from
                            user_info['age_to'] = age_to
                            self.storage.save_user_data()
                            del self.storage.user_states[user_id]
                            await context.bot.send_message(chat_id=chat_id,
                                                           text=f"✅ Возраст сохранен: {age_from}-{age_to} лет",
                                                           reply_markup=get_main_keyboard())
                        else:
                            await context.bot.send_message(chat_id=chat_id, text="❌ Неверный формат",
                                                           reply_markup=get_main_keyboard())
                    else:
                        await context.bot.send_message(chat_id=chat_id, text="❌ Неверный формат",
                                                       reply_markup=get_main_keyboard())
                except ValueError:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Неверный формат",
                                                   reply_markup=get_main_keyboard())

            elif state == 'waiting_for_city_to_delete':
                try:
                    city_index = int(text) - 1
                    cities = user_info.get('cities', [])

                    if 0 <= city_index < len(cities):
                        deleted_city = cities.pop(city_index)
                        user_info['cities'] = cities
                        self.storage.save_user_data()
                        del self.storage.user_states[user_id]
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"✅ Город '{deleted_city}' удален",
                            reply_markup=get_main_keyboard()
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="❌ Неверный номер города",
                            reply_markup=get_main_keyboard()
                        )
                except ValueError:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="❌ Введите номер города",
                        reply_markup=get_main_keyboard()
                    )

            else:
                del self.storage.user_states[user_id]
                await context.bot.send_message(chat_id=chat_id, text="❌ Ошибка", reply_markup=get_main_keyboard())
        else:
            await context.bot.send_message(chat_id=chat_id, text="Используйте кнопки для управления",
                                           reply_markup=get_main_keyboard())

