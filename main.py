"""Главный файл для запуска бота"""
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from config import TELEGRAM_BOT_TOKEN
from vk_api_manager import VKAPIManager
from storage import Storage
from search_engine import SearchEngine
from search_runner import SearchRunner
from handlers.commands import CommandHandlers

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Убираем логирование от библиотек
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('vk_api').setLevel(logging.WARNING)


def main() -> None:
    """Основная функция запуска бота"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram токен не установлен!")
        return

    # Инициализация компонентов
    vk_manager = VKAPIManager()
    if not vk_manager.sessions_count:
        logger.error("Не удалось инициализировать VK токены!")
        return

    storage = Storage()
    search_engine = SearchEngine(vk_manager, storage)
    search_runner = SearchRunner(vk_manager, storage, search_engine)
    command_handlers = CommandHandlers(storage, vk_manager, search_engine, search_runner)

    print("🟢 БОТ ОНЛАЙН")
    logger.info(f"Бот запущен с {vk_manager.sessions_count} VK токенами")

    async def post_init(application: Application) -> None:
        bot = application.bot
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Автоматическое возобновление поиска отключено")
        except Exception as e:
            logger.error(f"Ошибка в post_init: {e}")

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", command_handlers.start))
    application.add_handler(CommandHandler("search", command_handlers.handle_search))
    application.add_handler(CommandHandler("reset", command_handlers.handle_reset))

    # Регистрация обработчиков кнопок
    application.add_handler(MessageHandler(filters.Text("📍 Добавить города"), command_handlers.handle_add_cities))
    application.add_handler(MessageHandler(filters.Text("🔍 Добавить ключевые слова"), command_handlers.handle_add_keywords))
    application.add_handler(MessageHandler(filters.Text("🎯 Настройка возраста"), command_handlers.handle_age_settings))
    application.add_handler(MessageHandler(filters.Text("⚙️ Настройки"), command_handlers.handle_settings))
    application.add_handler(MessageHandler(filters.Text("🔎 Поиск"), command_handlers.handle_search))
    application.add_handler(MessageHandler(filters.Text("📊 Статистика"), command_handlers.handle_statistics))
    application.add_handler(MessageHandler(filters.Text("📥 Выгрузить Excel"), command_handlers.handle_download_excel))
    application.add_handler(MessageHandler(filters.Text("🗑 Удалить город"), command_handlers.handle_delete_city))
    application.add_handler(MessageHandler(filters.Text("🗑️ Удалить ключевые слова"), command_handlers.handle_delete_keywords))
    application.add_handler(MessageHandler(filters.Text("❓ Помощь"), command_handlers.handle_help))

    # Обработчик текстового ввода
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.handle_text_input))

    logger.info("Бот начал работу")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == '__main__':
    main()


