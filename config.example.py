"""Пример конфигурации бота"""
# Скопируйте этот файл в config.py и заполните своими данными

# VK токены для ротации (добавьте свои токены)
VK_TOKENS = [
    'vk1.a.ваш_токен_1',
    'vk1.a.ваш_токен_2',
    # Добавьте больше токенов для ротации
]

# Telegram Bot Token (получите у @BotFather)
TELEGRAM_BOT_TOKEN = 'ваш_telegram_bot_token'

# Разрешенные пользователи (юзернеймы без @)
ALLOWED_USERS = ['username1', 'username2']

# Настройки задержек для избежания блокировок
DELAY_BETWEEN_REQUESTS = (5, 10)
DELAY_BETWEEN_WALL_CHECKS = (3, 6)
DELAY_BETWEEN_USERS = (2, 5)
DELAY_AFTER_RATE_LIMIT = 15
DELAY_AFTER_FLOOD_CONTROL = 300
DELAY_BETWEEN_CITIES = 10
DELAY_BETWEEN_AGES = 5

# Минимальное количество пользователей в городе
MIN_USERS_IN_CITY = 50

# Файлы для хранения данных
DATA_FILE = 'user_data.json'
FOUND_USERS_FILE = 'found_users.json'
EXCEL_FILE = 'found_users.xlsx'
SEARCH_QUEUE_FILE = 'search_queue.json'

