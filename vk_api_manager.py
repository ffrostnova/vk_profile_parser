"""Менеджер для работы с VK API"""
import time
import logging
import vk_api
from vk_api.exceptions import ApiError
from typing import Optional, Tuple
from config import VK_TOKENS, DELAY_AFTER_FLOOD_CONTROL

logger = logging.getLogger(__name__)


class VKAPIManager:
    """Класс для управления VK API сессиями и ротацией токенов"""
    
    def __init__(self):
        self.vk_sessions = []
        self.current_token_index = 0
        self.token_stats = {}
        self.flood_control_active = False
        self.flood_control_until = 0
        self.init_sessions()
    
    def init_sessions(self) -> bool:
        """Инициализирует сессии VK для всех токенов"""
        self.vk_sessions = []
        self.token_stats = {}

        for i, token in enumerate(VK_TOKENS):
            if not token or token.startswith('vk1.a.ваш_токен_'):
                continue

            try:
                vk_session = vk_api.VkApi(token=token)
                vk = vk_session.get_api()
                self.vk_sessions.append({
                    'session': vk_session,
                    'api': vk,
                    'token': token,
                    'index': i,
                    'last_used': time.time(),
                    'requests_count': 0,
                    'error_count': 0,
                    'last_error_time': 0
                })
                self.token_stats[i] = {
                    'requests_count': 0,
                    'error_count': 0,
                    'last_used': time.time()
                }
                logger.info(f"Инициализирован VK API с токеном #{i}")
            except Exception as e:
                logger.error(f"Ошибка инициализации VK API с токеном #{i}: {e}")

        if not self.vk_sessions:
            logger.error("Не удалось инициализировать ни одного VK токена!")
            return False

        logger.info(f"Успешно инициализировано {len(self.vk_sessions)} VK токенов")
        return True
    
    def get_next_api(self) -> Tuple[Optional[object], Optional[int]]:
        """Возвращает следующий VK API объект с улучшенной ротацией токенов"""
        if not self.vk_sessions:
            if not self.init_sessions():
                return None, None

        # Проверяем глобальный флуд-контроль
        if self.flood_control_active and time.time() < self.flood_control_until:
            wait_time = self.flood_control_until - time.time()
            logger.warning(f"Глобальный флуд-контроль активен. Ожидание {wait_time:.1f} секунд")
            time.sleep(wait_time)
            self.flood_control_active = False

        # Выбираем токен с наименьшим количеством ошибок и запросов
        available_sessions = []
        current_time = time.time()

        for session in self.vk_sessions:
            # Пропускаем токены с ошибками в последние 5 минут
            if session['error_count'] >= 3 and current_time - session['last_error_time'] < 300:
                continue
            available_sessions.append(session)

        if not available_sessions:
            # Если все токены имеют ошибки, сбрасываем счетчики и используем все
            logger.warning("Все токены имеют ошибки, сбрасываем счетчики")
            for session in self.vk_sessions:
                session['error_count'] = 0
            available_sessions = self.vk_sessions

        # Выбираем токен с наименьшим количеством запросов и ошибок
        available_sessions.sort(key=lambda x: (x['error_count'], x['requests_count'], x['last_used']))

        selected_session = available_sessions[0]
        selected_session['requests_count'] += 1
        selected_session['last_used'] = time.time()

        logger.debug(
            f"Используется токен #{selected_session['index']}, запросов: {selected_session['requests_count']}, ошибок: {selected_session['error_count']}")

        return selected_session['api'], selected_session['index']
    
    def mark_token_error(self, token_index: int, error_code: Optional[int] = None) -> None:
        """Помечает токен как имеющий ошибку"""
        for session in self.vk_sessions:
            if session['index'] == token_index:
                session['error_count'] += 1
                session['last_error_time'] = time.time()
                logger.warning(f"Токен #{token_index} имеет {session['error_count']} ошибок")

                # При флуд-контроле активируем глобальную паузу
                if error_code == 9:  # Flood control
                    self.flood_control_active = True
                    self.flood_control_until = time.time() + DELAY_AFTER_FLOOD_CONTROL
                    logger.error(f"Обнаружен флуд-контроль! Глобальная пауза на {DELAY_AFTER_FLOOD_CONTROL} секунд")
                break
    
    def get_city_id(self, city_name: str) -> Optional[int]:
        """Получает ID города по названию через VK API"""
        vk, token_index = self.get_next_api()
        if not vk:
            logger.error("Нет доступных VK токенов для поиска города")
            return None

        if not city_name or not city_name.strip():
            return None

        try:
            logger.info(f"Поиск ID города через VK API: {city_name}")
            # Пробуем сначала поиск по России (country_id=1)
            result = vk.database.getCities(country_id=1, q=city_name, count=5)
            items = result.get('items', [])
            
            # Если не найдено в России, пробуем общий поиск
            if not items:
                logger.info(f"Город не найден в России, пробуем общий поиск: {city_name}")
                result = vk.database.getCities(q=city_name, count=5)
                items = result.get('items', [])
            
            if not items:
                logger.warning(f"Город не найден в VK: {city_name}")
                return None
            
            city_id = items[0]['id']
            logger.info(f"Найден ID города через VK API: {city_name} -> {city_id}")
            return city_id
        except ApiError as e:
            self.mark_token_error(token_index, e.code)
            logger.error(f"Ошибка VK API при поиске города {city_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при поиске города {city_name}: {e}")
            return None
    
    @property
    def sessions_count(self) -> int:
        """Возвращает количество активных сессий"""
        return len(self.vk_sessions)

