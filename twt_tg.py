import logging
import json
import os
import asyncio
import aiohttp
import ssl
from datetime import datetime

# =============================================================================
# 🕐 ФУНКЦИИ КОНВЕРТАЦИИ ДАТЫ
# =============================================================================

def format_twitter_date(twitter_date_str):
    """Конвертирует дату из Twitter формата в читаемый вид"""
    try:
        if not twitter_date_str:
            return ""
        
        # Twitter формат: "Fri Feb 14 15:30:03 +0000 2025"
        # Парсим дату
        dt = datetime.strptime(twitter_date_str, "%a %b %d %H:%M:%S %z %Y")
        
        # Конвертируем в локальное время (убираем timezone)
        dt_local = dt.replace(tzinfo=None)
        
        # Форматируем в читаемый вид
        formatted_date = dt_local.strftime("%d.%m.%Y в %H:%M")
        
        return formatted_date
        
    except Exception as e:
        logger.debug(f"Ошибка конвертации даты '{twitter_date_str}': {e}")
        return twitter_date_str  # Возвращаем оригинальную строку если не удалось конвертировать

# =============================================================================
# 🎨 СИСТЕМА ЛОГИРОВАНИЯ
# =============================================================================

class TelegramLogger:
    """Простая система логирования для Telegram модуля"""
    
    def __init__(self, log_file="telegram_logs.txt"):
        self.log_file = log_file
        self.setup_logging()
    
    def setup_logging(self):
        """Настройка базового логирования"""
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('aiohttp').setLevel(logging.WARNING)
    
    def _get_timestamp(self):
        """Получает временную метку"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _write_to_file(self, level, message):
        """Записывает сообщение в файл логов"""
        try:
            timestamp = self._get_timestamp()
            log_entry = f"[{timestamp}] {level}: {message}\n"
            
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception:
            pass
    
    def info(self, message):
        """Информационное сообщение"""
        print(f"ℹ️ {message}")
        self._write_to_file("INFO", message)
    
    def success(self, message):
        """Сообщение об успехе"""
        print(f"✅ {message}")
        self._write_to_file("SUCCESS", message)
    
    def error(self, message):
        """Ошибка"""
        print(f"❌ {message}")
        self._write_to_file("ERROR", message)
    
    def debug(self, message):
        """Отладочная информация (только в файл, не в консоль)"""
        self._write_to_file("DEBUG", message)

# Создаем глобальный экземпляр логгера
logger = TelegramLogger()

# =============================================================================
# 🎯 ОСНОВНЫЕ КОНСТАНТЫ
# =============================================================================

# Telegram настройки
TELEGRAM_BOT_TOKEN = "8483496130:AAEqjHf866To0OoHdqBs_5XvkBUnW_FYg4g"
TELEGRAM_CHANNEL_ID = "-1001774997176"  # ID канала с -100 в начале
TELEGRAM_THREAD_ID_INFO = "877545"      # ID топика для info
TELEGRAM_THREAD_ID_REPLIES = "882329"   # ID топика для replies
TELEGRAM_THREAD_ID_SUBS = "884871"      # ID топика для подписок

# Пути к файлам
DATA_DIR_INFO = "last_info"
DATA_DIR_REPLY = "last_reply"
DATA_DIR_SUBS = "new_subs"              # Папка с новыми подписками
SUBS_TARGET_ID = "1393231233370165330"  # ID для отслеживания подписок
INFO_TARGETS_FILE = os.path.join(DATA_DIR_INFO, "info_1406712007872221194.txt")
REPLY_TARGETS_FILE = os.path.join(DATA_DIR_REPLY, "reply_1406711873210023977.txt")

# Интервал проверки (в секундах)
CHECK_INTERVAL = 3600 

# =============================================================================
# 📱 TELEGRAM API ФУНКЦИИ
# =============================================================================

class TelegramBot:
    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session = None
        
    async def __aenter__(self):
        # Создаем SSL контекст без проверки сертификатов
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Создаем сессию с отключенной проверкой SSL
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def send_message(self, text, thread_id=None):
        """Отправляет сообщение в Telegram канал/топик"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.channel_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            
            # Если есть thread_id, добавляем его
            if thread_id:
                data["message_thread_id"] = thread_id
            
            logger.debug(f"Отправляем сообщение: {text[:100]}...")
            logger.debug(f"Данные для отправки: {data}")
            
            async with self.session.post(url, json=data) as response:
                response_text = await response.text()
                logger.debug(f"Ответ от Telegram API: {response.status} - {response_text}")
                
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        logger.success(f"Сообщение отправлено в Telegram")
                        return True
                    else:
                        logger.error(f"Telegram API ошибка: {result}")
                        return False
                else:
                    logger.error(f"HTTP ошибка: {response.status} - {response_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")
            return False
    
    async def send_photo(self, photo_url, caption, thread_id=None):
        """Отправляет фото с подписью в Telegram канал/топик"""
        try:
            url = f"{self.base_url}/sendPhoto"
            data = {
                "chat_id": self.channel_id,
                "photo": photo_url,
                "caption": caption,
                "parse_mode": "HTML"
            }
            
            # Если есть thread_id, добавляем его
            if thread_id:
                data["message_thread_id"] = thread_id
            
            logger.debug(f"Отправляем фото: {photo_url[:100]}...")
            logger.debug(f"Данные для отправки: {data}")
            
            async with self.session.post(url, json=data) as response:
                response_text = await response.text()
                logger.debug(f"Ответ от Telegram API: {response.status} - {response_text}")
                
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        logger.success(f"Фото с подписью отправлено в Telegram")
                        return True
                    else:
                        logger.error(f"Telegram API ошибка: {result}")
                        return False
                else:
                    logger.error(f"HTTP ошибка: {response.status} - {response_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Ошибка отправки фото в Telegram: {e}")
            return False
    
    async def test_connection(self):
        """Тестирует подключение к Telegram API"""
        try:
            url = f"{self.base_url}/getMe"
            async with self.session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        bot_info = result["result"]
                        logger.success(f"Telegram бот подключен: @{bot_info['username']}")
                        return True
                    else:
                        logger.error(f"Telegram API ошибка: {result}")
                        return False
                else:
                    logger.error(f"HTTP ошибка при тестировании: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Ошибка тестирования подключения: {e}")
            return False

# =============================================================================
# 📊 ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ
# =============================================================================

def load_info_targets():
    """Загружает список таргетов для отслеживания"""
    try:
        if not os.path.exists(INFO_TARGETS_FILE):
            logger.error(f"Файл {INFO_TARGETS_FILE} не найден")
            return []
        
        with open(INFO_TARGETS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        targets = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                targets.append(line)
        
        logger.info(f"Загружено {len(targets)} info таргетов: {', '.join(targets)}")
        return targets
        
    except Exception as e:
        logger.error(f"Ошибка загрузки info таргетов: {e}")
        return []

def load_reply_targets():
    """Загружает список таргетов для отслеживания replies"""
    try:
        if not os.path.exists(REPLY_TARGETS_FILE):
            logger.error(f"Файл {REPLY_TARGETS_FILE} не найден")
            return []
        
        with open(REPLY_TARGETS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        targets = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                targets.append(line)
        
        logger.info(f"Загружено {len(targets)} reply таргетов: {', '.join(targets)}")
        return targets
        
    except Exception as e:
        logger.error(f"Ошибка загрузки reply таргетов: {e}")
        return []

def get_user_info_file(username):
    """Получает путь к файлу с информацией о пользователе из папки new_info"""
    return os.path.join(DATA_DIR_INFO, "new_info", f"new_{username}_info.json")

def get_user_reply_file(username):
    """Получает путь к файлу с replies пользователя из папки new_replies"""
    return os.path.join(DATA_DIR_REPLY, "new_replies", f"new_{username}_replies.json")

def load_user_posts(username):
    """Загружает посты пользователя из JSON файла"""
    try:
        file_path = get_user_info_file(username)
        
        if not os.path.exists(file_path):
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            posts = json.load(f)
        
        if not isinstance(posts, list):
            return []
        
        return posts
        
    except Exception as e:
        logger.error(f"Ошибка загрузки постов для {username}: {e}")
        return []

def load_user_replies(username):
    """Загружает replies пользователя из JSON файла"""
    try:
        file_path = get_user_reply_file(username)
        
        if not os.path.exists(file_path):
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            replies = json.load(f)
        
        if not isinstance(replies, list):
            return []
        
        return replies
        
    except Exception as e:
        logger.error(f"Ошибка загрузки replies для {username}: {e}")
        return []

def format_post_message(username, post):
    """Форматирует пост - ссылка на FxTwitter для красивого превью"""
    try:
        post_id = post.get('id', '')  # Исправлено: было 'post_id', стало 'id'
        full_text = post.get('full_text', '')
        
        if not post_id or not full_text:
            return None
        
        # Проверяем, является ли пост репостом по наличию "RT" в full_text
        is_retweet = "RT @" in full_text
        
        # Создаем ссылку на FxTwitter для красивого превью в Telegram
        fxtwitter_url = f"https://fxtwitter.com/{username}/status/{post_id}"
        
        # Формируем сообщение в зависимости от типа поста
        if is_retweet:
            message = f'<a href="{fxtwitter_url}">New repost by @{username}</a>'
        else:
            message = f'<a href="{fxtwitter_url}">New post by @{username}</a>'
        
        return message
        
    except Exception as e:
        logger.error(f"Ошибка форматирования поста: {e}")
        return None

def format_reply_message(username, reply):
    """Форматирует reply - ссылка на FxTwitter для красивого превью"""
    try:
        reply_id = reply.get('reply_id', '')
        if not reply_id:
            return None
        
        # Создаем ссылку на FxTwitter для красивого превью в Telegram
        fxtwitter_url = f"https://fxtwitter.com/{username}/status/{reply_id}"
        
        # Формируем сообщение для reply
        message = f'<a href="{fxtwitter_url}">New replies by @{username}</a>'
        
        return message
        
    except Exception as e:
        logger.error(f"Ошибка форматирования reply: {e}")
        return None

def get_subs_directory():
    """Получает путь к папке с подписками для целевого ID"""
    return os.path.join(DATA_DIR_SUBS, SUBS_TARGET_ID)

def load_user_subscriptions():
    """Загружает все файлы подписок из папки new_subs/ID/"""
    try:
        subs_dir = get_subs_directory()
        
        if not os.path.exists(subs_dir):
            logger.info(f"Папка {subs_dir} не найдена")
            return []
        
        subscriptions = []
        
        # Проходим по всем файлам в папке
        for filename in os.listdir(subs_dir):
            if not filename.endswith('.json') or filename.startswith('.'):
                continue
                
            file_path = os.path.join(subs_dir, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    users = json.load(f)
                
                if not users or len(users) == 0:
                    logger.warning(f"Файл {filename} пустой, пропускаем")
                    continue
                
                # Получаем username таргета из имени файла
                found_by = filename.replace('new_', '').replace('.json', '')
                
                # Добавляем информацию о файле
                subscriptions.append({
                    'filename': filename,
                    'file_path': file_path,
                    'found_by': found_by,
                    'users': users
                })
                
                logger.info(f"Загружен файл {filename} с {len(users)} подписчиками от @{found_by}")
                
            except Exception as e:
                logger.error(f"Ошибка загрузки файла {filename}: {e}")
                continue
        
        return subscriptions
        
    except Exception as e:
        logger.error(f"Ошибка загрузки подписок: {e}")
        return []

# =============================================================================
# 🔄 ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ
# =============================================================================

async def process_new_posts(telegram_bot):
    """Обрабатывает новые посты всех таргетов из папки new_info"""
    try:
        # Загружаем список таргетов
        targets = load_info_targets()
        if not targets:
            logger.info("Нет таргетов для отслеживания")
            return
        
        total_new_posts = 0
        
        for username in targets:
            try:
                # Получаем все посты для пользователя из папки new_info
                posts = load_user_posts(username)
                
                if not posts:
                    continue                
                
                logger.info(f"Найдено {len(posts)} постов для @{username}")
                
                # Отправляем каждый пост
                for post in posts:
                    try:
                        # Форматируем сообщение
                        message = format_post_message(username, post)
                        
                        if not message:
                            continue
                        
                        # Отправляем в Telegram в топик для info
                        success = await telegram_bot.send_message(message, TELEGRAM_THREAD_ID_INFO)
                        
                        if success:
                            total_new_posts += 1
                            # Небольшая задержка между сообщениями
                            await asyncio.sleep(1)
                        else:
                            logger.error(f"Не удалось отправить пост {post['id']} для @{username}")
                    
                    except Exception as e:
                        logger.error(f"Ошибка обработки поста {post.get('id', 'N/A')}: {e}")
                        continue
                
                # После успешной отправки всех постов, НЕ удаляем файл из new_info
                # Файлы остаются в папке new_info для дальнейшего использования
                if posts:
                    logger.info(f"Обработано {len(posts)} постов для @{username}, файл сохранен в new_info")
                
            except Exception as e:
                logger.error(f"Ошибка обработки пользователя {username}: {e}")
                continue
        
        if total_new_posts > 0:
            logger.success(f"Обработано {total_new_posts} постов")
        else:
            logger.info("Постов не найдено")
            
    except Exception as e:
        logger.error(f"Ошибка обработки постов: {e}")

async def process_new_replies(telegram_bot):
    """Обрабатывает новые replies всех таргетов из папки new_replies"""
    try:
        # Загружаем список таргетов
        targets = load_reply_targets()
        if not targets:
            logger.info("Нет reply таргетов для отслеживания")
            return
        
        total_new_replies = 0
        
        for username in targets:
            try:
                # Получаем все replies для пользователя из папки new_replies
                replies = load_user_replies(username)
                
                if not replies:
                    continue                
                
                logger.info(f"Найдено {len(replies)} replies для @{username}")
                
                # Отправляем каждый reply
                for reply in replies:
                    try:
                        # Форматируем сообщение
                        message = format_reply_message(username, reply)
                        
                        if not message:
                            continue
                        
                        # Отправляем в Telegram в топик для replies
                        success = await telegram_bot.send_message(message, TELEGRAM_THREAD_ID_REPLIES)
                        
                        if success:
                            total_new_replies += 1
                            # Небольшая задержка между сообщениями
                            await asyncio.sleep(1)
                        else:
                            logger.error(f"Не удалось отправить reply {reply.get('reply_id', 'N/A')} для @{username}")
                    
                    except Exception as e:
                        logger.error(f"Ошибка обработки reply {reply.get('reply_id', 'N/A')}: {e}")
                        continue
                
                # После успешной отправки всех replies, НЕ удаляем файл из new_replies
                # Файлы остаются в папке new_replies для дальнейшего использования
                if replies:
                    logger.info(f"Обработано {len(replies)} replies для {username}, файл сохранен в new_replies")
                
            except Exception as e:
                logger.error(f"Ошибка обработки reply пользователя {username}: {e}")
                continue
        
        if total_new_replies > 0:
            logger.success(f"Обработано {total_new_replies} replies")
        else:
            logger.info("Replies не найдено")
            
    except Exception as e:
        logger.error(f"Ошибка обработки replies: {e}")

async def process_new_subscriptions(telegram_bot):
    """Обрабатывает новые подписки из папки new_subs для целевого ID"""
    try:
        logger.info("🔄 Начинаем проверку новых подписок...")
        
        # Загружаем все файлы подписок
        subscriptions = load_user_subscriptions()
        
        if not subscriptions:
            logger.info("Нет новых подписок для обработки")
            return
        
        total_subscriptions_sent = 0
        
        for subscription in subscriptions:
            try:
                found_by = subscription['found_by']
                users = subscription['users']
                
                logger.info(f"Обрабатываем {len(users)} подписчиков от @{found_by}")
                
                # Отправляем каждого подписчика отдельно с фото
                for i, user_data in enumerate(users, 1):
                    try:
                        avatar_url = user_data[0] if len(user_data) > 0 else ""
                        created_at = user_data[1] if len(user_data) > 1 else ""
                        username = user_data[2] if len(user_data) > 2 else ""
                        name = user_data[3] if len(user_data) > 3 else ""
                        bio = user_data[4] if len(user_data) > 4 else ""
                        followers = user_data[5] if len(user_data) > 5 else 0
                        banner_url = user_data[6] if len(user_data) > 6 else ""
                        
                        # Формируем подпись для фото в HTML формате
                        caption = f"<b>Новый подписка от {found_by}</b>\n\n"
                        caption += f"<b>@{username}</b>"
                        if name:
                            caption += f" ({name})"
                        caption += "\n"
                        if bio:
                            caption += f"<code>{bio}</code>\n\n"
                        if followers:
                            caption += f"- Подписчиков: {followers:,}\n"
                        if created_at:
                            formatted_date = format_twitter_date(created_at)
                            caption += f"- Создан: {formatted_date}\n"
                        
                        # Добавляем ссылку на профиль
                        profile_url = f"https://x.com/{username}"
                        caption += f"\n🔗 <a href='{profile_url}'>Профиль Twitter</a>"
                        
                        # Отправляем фото с подписью
                        if banner_url:
                            success = await telegram_bot.send_photo(banner_url, caption, TELEGRAM_THREAD_ID_SUBS)
                            if success:
                                logger.success(f"Подписчик @{username} отправлен с обложкой профиля")
                                total_subscriptions_sent += 1
                            else:
                                logger.error(f"Не удалось отправить обложку для @{username}")
                        elif avatar_url:
                            # Если нет обложки, используем аватар как запасной вариант
                            success = await telegram_bot.send_photo(avatar_url, caption, TELEGRAM_THREAD_ID_SUBS)
                            if success:
                                logger.success(f"Подписчик @{username} отправлен с аватаром")
                                total_subscriptions_sent += 1
                            else:
                                logger.error(f"Не удалось отправить аватар для @{username}")
                        else:
                            logger.warning(f"Нет ни обложки, ни аватара для @{username}, пропускаем")
                        
                        # Небольшая задержка между сообщениями
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Ошибка обработки подписчика {i}: {e}")
                        continue
                
                # После успешной отправки всех подписок, НЕ удаляем файлы из new_subs
                # Файлы остаются в папке new_subs для дальнейшего использования
                # (логика идентична info и replies модулям)
                
            except Exception as e:
                logger.error(f"Ошибка обработки подписок {subscription['filename']}: {e}")
                continue
        
        if total_subscriptions_sent > 0:
            logger.success(f"Обработано {total_subscriptions_sent} подписчиков")
        else:
            logger.info("Подписчики не найдены")
            
    except Exception as e:
        logger.error(f"Ошибка обработки подписок: {e}")

async def main_loop():
    """Основной цикл работы модуля"""
    logger.info("🚀 Запуск Telegram модуля для отслеживания постов, replies и подписок")
    
    # Проверяем существование необходимых папок
    for directory in [DATA_DIR_INFO, DATA_DIR_REPLY, DATA_DIR_SUBS]:
        if not os.path.exists(directory):
            logger.error(f"❌ Папка {directory} не найдена")
            return
    
    # Инициализируем Telegram бота
    async with TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID) as telegram_bot:
        # Тестируем подключение
        if not await telegram_bot.test_connection():
            logger.error("❌ Не удалось подключиться к Telegram API")
            return
        
        logger.success("✅ Telegram бот подключен успешно")
        
        # Основной цикл
        while True:
            try:
                logger.info("🔄 Начинаем проверку новых постов...")
                
                # Обрабатываем новые посты (info)
                await process_new_posts(telegram_bot)
                
                logger.info("🔄 Начинаем проверку новых replies...")
                
                # Обрабатываем новые replies
                await process_new_replies(telegram_bot)
                
                logger.info("🔄 Начинаем проверку новых подписок...")
                
                # Обрабатываем новые подписки
                await process_new_subscriptions(telegram_bot)
                
                logger.info(f"⏰ Следующая проверка через 1 час и 7 минут")
                await asyncio.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("🛑 Получен сигнал остановки")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в основном цикле: {e}")
                logger.info("⏰ Повторная попытка через 30 секунд...")
                await asyncio.sleep(30)

# =============================================================================
# 🚀 ТОЧКА ВХОДА
# =============================================================================

def cleanup_old_logs():
    """Очищает старые логи, оставляя только последние 1000 строк"""
    try:
        log_file = "telegram_logs.txt"
        if os.path.exists(log_file) and os.path.getsize(log_file) > 1024 * 1024:  # 1MB
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Оставляем только последние 1000 строк
            if len(lines) > 1000:
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-1000:])
                logger.info("🧹 Старые логи очищены")
    except Exception:
        pass

if __name__ == "__main__":
    try:
        # Очищаем старые логи перед запуском
        cleanup_old_logs()
        
        # Запускаем основной цикл
        logger.info("🚀 Запуск основного модуля...")
        asyncio.run(main_loop())
            
    except KeyboardInterrupt:
        logger.info("🛑 Модуль остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        logger.info("👋 Telegram модуль завершил работу")
