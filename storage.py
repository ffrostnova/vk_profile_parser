"""Модуль для работы с хранением данных"""
import os
import json
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from config import DATA_FILE, FOUND_USERS_FILE, EXCEL_FILE, SEARCH_QUEUE_FILE

logger = logging.getLogger(__name__)


class Storage:
    """Класс для работы с хранилищем данных"""
    
    def __init__(self):
        self.user_data: Dict[int, Dict] = {}
        self.search_queue: Dict[int, Dict] = {}
        self.user_states: Dict[int, str] = {}
        self.load_all()
    
    def load_all(self) -> None:
        """Загружает все данные из файлов"""
        self.user_data = self.load_user_data()
        self.search_queue = self.load_search_queue()
    
    def load_user_data(self) -> Dict[int, Dict]:
        """Загружает данные пользователей из файла"""
        if not os.path.exists(DATA_FILE):
            return {}
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных: {e}")
            return {}
    
    def save_user_data(self) -> None:
        """Сохраняет данные пользователей в файл"""
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.user_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных: {e}")
    
    def load_search_queue(self) -> Dict[int, Dict]:
        """Загружает очередь поиска из файла"""
        if not os.path.exists(SEARCH_QUEUE_FILE):
            return {}
        try:
            with open(SEARCH_QUEUE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Ошибка при загрузке очереди поиска: {e}")
            return {}
    
    def save_search_queue(self) -> None:
        """Сохраняет очередь поиска в файл"""
        try:
            with open(SEARCH_QUEUE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.search_queue, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка при сохранении очереди поиска: {e}")
    
    def get_or_init_user_data(self, user_id: int) -> Dict:
        """Получает или инициализирует данные пользователя"""
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                'cities': [],
                'keywords': [],
                'age_from': 14,
                'age_to': 35,
                'status': 'idle',
                'check_wall': False
            }
            self.save_user_data()
        return self.user_data[user_id]
    
    def load_found_users(self) -> List[Dict]:
        """Загружает найденных пользователей из файла"""
        if not os.path.exists(FOUND_USERS_FILE):
            return []
        try:
            with open(FOUND_USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Ошибка при загрузке найденных пользователей: {e}")
            return []
    
    def save_found_user(self, user: Dict, city_name: Optional[str] = None) -> None:
        """Сохраняет найденного пользователя в JSON файл"""
        try:
            found_users = self.load_found_users()
            user_id = user.get('id')

            if not any(u.get('id') == user_id for u in found_users):
                user_with_date = {
                    'id': user_id,
                    'name': user.get('name', ''),
                    'profile_url': user.get('profile_url', f"https://vk.com/id{user_id}"),
                    'city_id': user.get('city_id'),
                    'city_name': city_name or 'Неизвестно',
                    'found_date': datetime.now().isoformat(),
                    'matches': user.get('matches', []),
                    'bdate': user.get('bdate', 'не указана'),
                    'photo_url': user.get('photo_url')
                }
                found_users.append(user_with_date)

                with open(FOUND_USERS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(found_users, f, ensure_ascii=False, indent=2)
                logger.info(f"Сохранен пользователь в JSON: {user['name']}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении пользователя в JSON: {e}")
    
    def save_to_excel(self, user: Dict, city_name: str) -> None:
        """Сохраняет найденного пользователя в Excel файл"""
        try:
            profile_url = user.get('profile_url', '')
            user_id = user.get('id', '')
            user_name = user.get('name', '')

            matches_info = []
            for match in user.get('matches', []):
                keyword = match.get('keyword', '')
                field = match.get('field', '')
                text_preview = match.get('text', '')[:100] + '...' if len(match.get('text', '')) > 100 else match.get('text', '')
                matches_info.append(f"{keyword} → {field}: {text_preview}")

            matches_str = '\n'.join(matches_info) if matches_info else 'Не указано'
            found_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            new_data = {
                'Дата обнаружения': [found_date],
                'Ссылка на профиль': [profile_url],
                'Маркер': [user_id],
                'ID пользователя': [user_id],
                'Имя': [user_name],
                'Город': [city_name],
                'Дата рождения': [user.get('bdate', 'не указана')],
                'маркер': [matches_str]
            }

            df_new = pd.DataFrame(new_data)

            if os.path.exists(EXCEL_FILE):
                try:
                    df_existing = pd.read_excel(EXCEL_FILE)
                    if user_id not in df_existing['Маркер'].values:
                        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
                            df_combined.to_excel(writer, index=False, sheet_name='Найденные пользователи')
                            worksheet = writer.sheets['Найденные пользователи']
                            self._adjust_column_width(worksheet)
                        logger.debug(f"Добавлен пользователь в Excel: {user_name}")
                    else:
                        logger.debug(f"Пользователь {user_name} уже существует в Excel, пропускаем дублирование")
                except Exception as e:
                    self._save_new_excel_file(df_new)
            else:
                self._save_new_excel_file(df_new)

        except Exception as e:
            logger.error(f"Ошибка при сохранении в Excel: {e}")
    
    def _save_new_excel_file(self, df: pd.DataFrame) -> None:
        """Создает новый Excel файл"""
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Найденные пользователи')
            worksheet = writer.sheets['Найденные пользователи']
            self._adjust_column_width(worksheet)
        logger.info("Создан новый Excel файл")
    
    def _adjust_column_width(self, worksheet) -> None:
        """Настраивает ширину колонок по длине текста"""
        try:
            for column in worksheet.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)

                for cell in column:
                    try:
                        if cell.value:
                            cell_lines = str(cell.value).split('\n')
                            max_line_length = max(len(line) for line in cell_lines)
                            max_length = max(max_length, max_line_length)
                    except:
                        pass

                adjusted_width = min(max_length + 3, 100)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        except Exception as e:
            logger.error(f"Ошибка при настройке ширины колонок: {e}")


