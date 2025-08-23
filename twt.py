import logging
import json
import time
import os
import threading
import requests
import discord
from discord.ext import commands
import asyncio
from discord import app_commands
from datetime import datetime
import re
import glob
import shutil
# import telegram  # Telegram модуль удален
# from telegram.ext import Updater  # Telegram модуль удален

# =============================================================================
# 🎨 СИСТЕМА ЛОГИРОВАНИЯ
# =============================================================================

class BotLogger:
    """Красивая система логирования для Discord бота"""
    
    def __init__(self, log_file="bot_logs.txt"):
        self.log_file = log_file
        self.bot = None
        self.log_buffer = []  # Буфер для группировки логов
        self.session_start_time = datetime.now()
        self.setup_logging()
    
    def setup_logging(self):
        """Настройка базового логирования"""
        logging.basicConfig(level=logging.CRITICAL)
        logging.getLogger('discord').setLevel(logging.CRITICAL)
        logging.getLogger('discord.client').setLevel(logging.CRITICAL)
        logging.getLogger('discord.gateway').setLevel(logging.CRITICAL)
        logging.getLogger('aiohttp').setLevel(logging.CRITICAL)

    # Метод set_bot удален - Discord логирование отключено
    
    def _get_timestamp(self):
        """Получает красивую временную метку"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _write_to_file(self, level, message, emoji=""):
        """Записывает сообщение в файл логов"""
        try:
            timestamp = self._get_timestamp()
            log_entry = f"[{timestamp}] {emoji} {level}: {message}\n"
            
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            # Не используем logger для записи ошибок логгера, чтобы избежать рекурсии
            pass
    
    def _add_to_buffer(self, level, message, emoji=""):
        """Добавляет лог в буфер для группировки"""
        timestamp = self._get_timestamp()
        log_entry = f"[{timestamp}] {emoji} {level}: {message}"
        self.log_buffer.append(log_entry)

    
    def clear_log_buffer(self):
        """Очищает буфер логов"""
        self.log_buffer.clear()
        print("🧹 Буфер логов очищен")
    
    
    def info(self, message, emoji="ℹ️"):
        """Информационное сообщение"""
        print(f"{emoji} {message}")
        self._write_to_file("INFO", message, emoji)
        self._add_to_buffer("INFO", message, emoji)
    
    def success(self, message, emoji="✅"):
        """Сообщение об успехе"""
        print(f"{emoji} {message}")
        self._write_to_file("SUCCESS", message, emoji)
        self._add_to_buffer("SUCCESS", message, emoji)
    
    def warning(self, message, emoji="⚠️"):
        """Предупреждение"""
        print(f"{emoji} {message}")
        self._write_to_file("WARNING", message, emoji)
        self._add_to_buffer("WARNING", message, emoji)
    
    def error(self, message, emoji="❌"):
        """Ошибка (логируется в файл)"""
        print(f"{emoji} {message}")
        self._write_to_file("ERROR", message, emoji)
        self._add_to_buffer("ERROR", message, emoji)
    
    def debug(self, message, emoji="🔍"):
        """Отладочная информация"""
        print(f"{emoji} {message}")
        self._write_to_file("DEBUG", message, emoji)
        self._add_to_buffer("DEBUG", message, emoji)
    
    def scan_start(self, module_name):
        """Начало сканирования модуля"""
        message = f"🔄 Начинаем сканирование {module_name}..."
        self.info(message, "🔄")
    
    def scan_complete(self, module_name, results=""):
        """Завершение сканирования модуля"""
        message = f"✅ Сканирование {module_name} завершено"
        if results:
            message += f" - {results}"
        self.success(message, "✅")
    
    def module_error(self, module_name, error):
        """Ошибка в модуле"""
        message = f"❌ Ошибка в модуле {module_name}: {error}"
        self.error(message, "❌")
    
    def discord_operation(self, operation, status, details=""):
        """Операция с Discord"""
        emoji = "✅" if status else "❌"
        message = f"Discord {operation}: {'успешно' if status else 'ошибка'}"
        if details:
            message += f" - {details}"
        self.info(message, emoji)
    
    def file_operation(self, operation, file_path, status, details=""):
        """Операция с файлом"""
        emoji = "✅" if status else "❌"
        message = f"Файл {operation}: {file_path} - {'успешно' if status else 'ошибка'}"
        if details:
            message += f" - {details}"
        self.info(message, emoji)
    
    def session_separator(self):
        """Красная разделительная строка между сессиями"""
        separator = "🔴" + "="*80 + "🔴"
        print(f"\n{separator}")
        self._write_to_file("SESSION", separator, "🔴")
        self._add_to_buffer("SESSION", separator, "🔴")

# Создаем глобальный экземпляр логгера
logger = BotLogger()

# =============================================================================
# 🎯 ОСНОВНЫЕ КОНСТАНТЫ И НАСТРОЙКИ ДЛЯ DISCORD
# =============================================================================

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
tree = bot.tree  # Для регистрации слэш-команд
bot_ready = False  # Флаг готовности бота
# telegram_loop больше не нужен - используем общий Discord event loop

# Ссылка на бота больше не нужна - Discord логирование отключено

# --- Константы и настройки ---
TARGETS_FILE = "targets.txt"                            # Для обратной совместимости
DIFF_CHATS_FILE = "diff_chats.json"                     # Каналы и их списки
DATA_DIR = "data"                                       # Списки подписок
NEW_DIR = "new_subs"                                    # Новые подписки для отправки
DATA_DIR_BIG = "big_follow"                          # Списки больших подписчиков
OLD_DIR_BIG = "big_follow/old_followers"             # Старые данные больших подписчиков
NEW_DIR_BIG = "big_follow/new_big"                   # Новые большие подписчики для отправки 
DISCORD_CHANNEL_ID = 1391418960494465084                # Дефолтный канал (legacy)
DISCORD_CHANNEL_ID_BIG_FOLLOWERS = 1393642946749927525  # Канал с отслеживанием больших подписчиков
BOT_TOKEN = "MTI5Nzk0MTE4Mzg3MTMyNDIyMg.G7tFEv.Sj-8iq9xCxG5tbOBIGJD7HOZISuZeN1gfCzfMA"

# --- Константы для ответов (reply) и панели с кнопками ---
DATA_DIR_REPLY = "last_reply"                           # Списки ответов
NEW_DIR_REPLY = "last_reply/new_replies"               # Новые ответы для отправки
REPLY_TARGETS_FILE = "last_reply/reply.txt"           # Список пользователей для отслеживания ответов
REPLY_PANEL_MESSAGE_ID_FILE = "last_reply/reply_panel_message_id.txt"  # Файл для хранения ID сообщения панели
DISCORD_CHANNEL_ID_REPLIES = 1402973659647184967        # Канал для отправки ответов

# Канал, где размещается embed с кнопкой создания каналов (панель управления)
CONTROL_PANEL_CHANNEL_ID = 1403414188235165776
# --- Константы для info-модуля ---
DATA_DIR_INFO = "last_info"                              # Списки info-таргетов
NEW_DIR_INFO = "last_info/new_info"                      # Новые info-события (если потребуется буфер)
INFO_PANEL_CHANNEL_ID = 1404545036946898944              # Канал панели info
INFO_CHANNELS_FILE = os.path.join(DATA_DIR_INFO, "info_channels.json")

# =============================================================================
# 🎯 ОСНОВНЫЕ КОНСТАНТЫ И НАСТРОЙКИ ДЛЯ TELEGRAM
# =============================================================================

# Главный канал для общего использования (только Discord)
# MAIN_INFO_CHANNEL_ID = 1405554698769010780  # bitcoin-eco канал - УДАЛЕН, канал не существует

logger.info("🚀 Telegram модуль удален - работаем только с Discord")
logger.info("✅ Бот будет отправлять сообщения только в Discord каналы")

# =============================================================================
# 📱 TELEGRAM МОДУЛЬ УДАЛЕН
# =============================================================================
# Функция send_telegram_welcome_message удалена - заменена на статус запуска в on_ready


# =============================================================================
# 🐦 TWITTER API НАСТРОЙКИ
# =============================================================================

# Общие cookies для всех запросов
TWITTER_COOKIES = {
    'kdt': 'tIUH0HtfnnAmHOjGeZ8Vg2sFmIBty0MPcE035SEA',
    'night_mode': '2',
    '_monitor_extras': '{"deviceId":"IHd_l_bj9G0WmWokVdooqa","eventId":7,"sequenceNumber":7}',
    'amp_669cbf': '19c36faa-457b-42a5-ae11-f662b20c8ee5.MTljMzZmYWEtNDU3Yi00MmE1LWFlMTEtZjY2MmIyMGM4ZWU1..1i5ghfh2q.1i5ghfh2r.5.0.5',
    'twtr_pixel_opt_in': 'Y',
    'amp_56bf9d': '19c36faa-457b-42a5-ae11-f662b20c8ee5...1i5lo7ltt.1i5lom3r1.1.1.2',
    'd_prefs': 'MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw',
    'personalization_id': '"v1_RsvteDXPzLImJVYFKULH/w=="',
    'guest_id_ads': 'v1%3A174724380802786926',
    'guest_id_marketing': 'v1%3A174724380802786926',
    'cf_clearance': '5BVvpIzix7NKCMm.4xf.2CMkEM6s0V9KkCHM1U7ADbk-1750182280-1.2.1.1-1rsRRpEXCSX3mERcZi8bW5GaWFgY_NM3SNtur8ltNRl00fX7UPNt0mCMNRssyr22bRNeZU2M3xZpsFHU8_KU6x.edmyJF3cijNfRWQrSI.9tOFhuK.bqOuSCcUSzRc1HvvaH3TQZQfQQ5laamYtGvFV6DDi6fZ8NlJVYTV22UkRer_ado.Fc3twwmZVxg7l2XFu5AFGnV6DRgFliK6snSF4b3qpCVhJNO5gKUNwJp1NUkXTzuPET5jwggw7MqoDKD_WpXMJBSZ6EcEutwrKYpNN6eatRgy_1bmqqidsQDPiS4RdgDde8K2tmqr1jAfINazD49YOpMdzy.eaSkgXMoVzjjr20EgUtmUwbs7bwUPVNDoGoJmiHiKXu16a8aXoG',
    'lang': 'ru',
    'ok_global': '{"_expire":{}}',
    'ok_default': '{"_expire":{}}',
    'ok_okg': '{"_expire":{},"currentMedia":"xl"}',
    'first_ref': 'https%3A%2F%2Fwww.google.com%2F',
    'auth_multi': '"1527960562235236354:a380486e2a6bfcfd3ce3c38e99c27c1858fe0caa|1823675166096023555:fe44688dff6387dfde0cb99a63a29106e82e28b5"',
    'auth_token': 'bd079fea2a671c42a6e95e00707198d1779ae867',
    'twid': 'u%3D1538858660801269763',
    'guest_id': 'v1%3A175191006134176598',
    'ct0': 'ec97a7a1facfcdf30c6261b372e21dfc65fef7290a3d8dddbd09401afa65d1b85f565cca1fe59ddf4a14a02a57f9cfa91fa6a320e48a8408a1c8058fb7afceb8ef0fb08eae2194e7dd1d169ed910d123',
    '__cf_bm': 'cOwqzv1OSU44Dqsr8WAitl8R0eVHFw00.D6EnvSr5ak-1752134796-1.0.1.1-Elv9.G2rYwTqZb63HZChVds6eoywv8rZDgAG2wAbE9D.Vvg8aftZ3vct5_J19Ze.qxQoB4RDK8oZIsZMcOxCERP7aQSYwrtiknrEzVhbG8o',
}
headers_id = {
    'accept': '*/*',
    'accept-language': 'en,en-US;q=0.9,ru-RU;q=0.8,ru;q=0.7',
    'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'content-type': 'application/json',
    'priority': 'u=1, i',
    'referer': 'https://x.com/{name_user}/following',
    'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
    'sec-ch-ua-arch': '"arm"',
    'sec-ch-ua-bitness': '"64"',
    'sec-ch-ua-full-version': '"137.0.7151.120"',
    'sec-ch-ua-full-version-list': '"Google Chrome";v="137.0.7151.120", "Chromium";v="137.0.7151.120", "Not/A)Brand";v="24.0.0.0"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"macOS"',
    'sec-ch-ua-platform-version': '"15.5.0"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    'x-client-transaction-id': 'snPRi4+N5Y8nEj6DbrPwwQ8ztyKZlYl3clRCjCPeF+QpnSvZnfYyBFAJ/IACUC+DIuejkraQArQC0UMF8RmEvH7OHKTAsQ',
    'x-csrf-token': 'ec97a7a1facfcdf30c6261b372e21dfc65fef7290a3d8dddbd09401afa65d1b85f565cca1fe59ddf4a14a02a57f9cfa91fa6a320e48a8408a1c8058fb7afceb8ef0fb08eae2194e7dd1d169ed910d123',
    'x-twitter-active-user': 'yes',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-client-language': 'ru',
    'x-xp-forwarded-for': '675817705eb7c59b8f687b74a8154a7728aaec20935a54ccee0963f18637e88e6dfb2287095428f2ee6047d5fa8606b206df9459959c67f6135585761e01fc987096adc292fd914994abf0f8c82f3c0708cc4f06d8372556315e9c9ac3d15254559b21aa5677618a4116d589f3d4d4253910015393c7e9a34a274856fa88d8389e9ac3da3f065fac46ac3196ab0a48926fd8a250b9eef316d70f912748ac792ae9e9540bcdb20fa754df6648cb6b25f5722b00885bf79fdf2613f307185ab590b93f8875f3963ebd1c6cba0d3483f74c3f2cb528ea461e4864ba182e0e8d6bc50f27cdbab3959e946e26a986d11513a6a37e7e6e56229d0c33307205d701e1175b',
    'cookie': 'kdt=tIUH0HtfnnAmHOjGeZ8Vg2sFmIBty0MPcE035SEA; night_mode=2; _monitor_extras={"deviceId":"IHd_l_bj9G0WmWokVdooqa","eventId":7,"sequenceNumber":7}; amp_669cbf=19c36faa-457b-42a5-ae11-f662b20c8ee5.MTljMzZmYWEtNDU3Yi00MmE1LWFlMTEtZjY2MmIyMGM4ZWU1..1i5ghfh2q.1i5ghfh2r.5.0.5; twtr_pixel_opt_in=Y; amp_56bf9d=19c36faa-457b-42a5-ae11-f662b20c8ee5...1i5lo7ltt.1i5lom3r1.1.1.2; d_prefs=MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw; personalization_id="v1_RsvteDXPzLImJVYFKULH/w=="; guest_id_ads=v1%3A174724380802786926; guest_id_marketing=v1%3A174724380802786926; cf_clearance=5BVvpIzix7NKCMm.4xf.2CMkEM6s0V9KkCHM1U7ADbk-1750182280-1.2.1.1-1rsRRpEXCSX3mERcZi8bW5GaWFgY_NM3SNtur8ltNRl00fX7UPNt0mCMNRssyr22bRNeZU2M3xZpsFHU8_KU6x.edmyJF3cijNfRWQrSI.9tOFhuK.bqOuSCcUSzRc1HvvaH3TQZQfQQ5laamYtGvFV6DDi6fZ8NlJVYTV22UkRer_ado.Fc3twwmZVxg7l2XFu5AFGnV6DRgFliK6snSF4b3qpCVhJNO5gKUNwJp1NUkXTzuPET5jwggw7MqoDKD_WpXMJBSZ6EcEutwrKYpNN6eatRgy_1bmqqidsQDPiS4RdgDde8K2tmqr1jAfINazD49YOpMdzy.eaSkgXMoVzjjr20EgUtmUwbs7bwUPVNDoGoJmiHiKXu16a8aXoG; lang=ru; ok_global={"_expire":{}}; ok_default={"_expire":{}}; ok_okg={"_expire":{},"currentMedia":"xl"}; first_ref=https%3A%2F%2Fwww.google.com%2F; auth_multi="1527960562235236354:a380486e2a6bfcfd3ce3c38e99c27c1858fe0caa|1823675166096023555:fe44688dff6387dfde0cb99a63a29106e82e28b5"; auth_token=bd079fea2a671c42a6e95e00707198d1779ae867; twid=u%3D1538858660801269763; guest_id=v1%3A175191006134176598; ct0=ec97a7a1facfcdf30c6261b372e21dfc65fef7290a3d8dddbd09401afa65d1b85f565cca1fe59ddf4a14a02a57f9cfa91fa6a320e48a8408a1c8058fb7afceb8ef0fb08eae2194e7dd1d169ed910d123; __cf_bm=cOwqzv1OSU44Dqsr8WAitl8R0eVHFw00.D6EnvSr5ak-1752134796-1.0.1.1-Elv9.G2rYwTqZb63HZChVds6eoywv8rZDgAG2wAbE9D.Vvg8aftZ3vct5_J19Ze.qxQoB4RDK8oZIsZMcOxCERP7aQSYwrtiknrEzVhbG8o',
}
params_id = {
    'variables': '{"screen_name":"{name_user}"}',
    'features': '{"responsive_web_grok_bio_auto_translation_is_enabled":false,"hidden_profile_subscriptions_enabled":true,"payments_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"subscriptions_verification_info_is_identity_verified_enabled":true,"subscriptions_verification_info_verified_since_enabled":true,"highlights_tweets_tab_ui_enabled":true,"responsive_web_twitter_article_notes_tab_enabled":true,"subscriptions_feature_can_gift_premium":true,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"responsive_web_graphql_timeline_navigation_enabled":true}',
    'fieldToggles': '{"withAuxiliaryUserLabels":true}',
}



# --- cURL для получения данных о подписках ---

cookies_following    = {
    'ok_okg': '{"_expire":{},"currentMedia":"lg"}',
    'ok_global': '{"_expire":{}}',
    'ok_default': '{"_expire":{}}',
    'kdt': 'tIUH0HtfnnAmHOjGeZ8Vg2sFmIBty0MPcE035SEA',
    'night_mode': '2',
    '_monitor_extras': '{"deviceId":"IHd_l_bj9G0WmWokVdooqa","eventId":7,"sequenceNumber":7}',
    'amp_669cbf': '19c36faa-457b-42a5-ae11-f662b20c8ee5.MTljMzZmYWEtNDU3Yi00MmE1LWFlMTEtZjY2MmIyMGM4ZWU1..1i5ghfh2q.1i5ghfh2r.5.0.5',
    'twtr_pixel_opt_in': 'Y',
    'amp_56bf9d': '19c36faa-457b-42a5-ae11-f662b20c8ee5...1i5lo7ltt.1i5lom3r1.1.1.2',
    'd_prefs': 'MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw',
    'personalization_id': '"v1_RsvteDXPzLImJVYFKULH/w=="',
    '__cuid': 'b6ed2207bbb6467fb2d91f43eaf62a91',
    'first_ref': 'https%3A%2F%2Fx.com%2Fsearch%3Fq%3D%2524hosico%26src%3Drecent_search_click',
    'guest_id_ads': 'v1%3A175232397208590930',
    'guest_id_marketing': 'v1%3A175232397208590930',
    'lang': 'ru',
    'ok_global': '{"_expire":{}}',
    'ok_default': '{"_expire":{}}',
    'ads_prefs': '"HBERAAA="',
    'auth_multi': '"1527960562235236354:a380486e2a6bfcfd3ce3c38e99c27c1858fe0caa|1823675166096023555:fe44688dff6387dfde0cb99a63a29106e82e28b5"',
    'auth_token': 'bd079fea2a671c42a6e95e00707198d1779ae867',
    'guest_id': 'v1%3A175485905244719279',
    'twid': 'u%3D1538858660801269763',
    'ct0': 'c67939e914a041fc74e33371011472d9d16504b5040be5d9047221ac0ea2ee2a7b7a5f1378ef215321f11e29289877fad9e96ecbc0b3aab084671cbf449adf0e2f12f88a8906eead2ae22696f576b570',
    'cf_clearance': 'ReQm3hb53.ShoGFPMT7x52PDxsEb4pLWbRzt7F8n6wk-1754927951-1.2.1.1-mrn6QkHWwyIHungjByaw9E4xzQCy16paFet3DWlTgeDnWSr1_yxClGbdKSlCnhKblnaSV38eXCOINRBmyIbTdURDovYb8UuDVSexlw10kg.CKt9M_y2_MCJMo18gktiurgfIHgKzHVTgb16vPjUzZeY.70ow_5NUm.9sNtQ2RRYjZPE0O7EU7X23h.Hzy4MAa4z6b_60xM3OambobxFz3hSXJdiw_8_22rb7SevodTw',
    '_twitter_sess': 'BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCO9v25mYAToMY3NyZl9p%250AZCIlNjkyOGI5M2JmNTBkMzQ0MjNkNWYxMGUwZTNhODNmOTY6B2lkIiVmNWZm%250AYzg4MzE4ZGI5Mzg3MGIxMjVhY2VhNTYyMTRjYg%253D%253D--29273ef817f8e65030e5c50daceaca34d6bf6069',
    'ok_okg': '{"_expire":{},"currentMedia":"xl"}',
    '__cf_bm': '5tVovvw3xBVrymBxRt3290aGv75wwqPUPmQcKB_gbM4-1755290244-1.0.1.1-39IXRx1bS1wLhuu0pxjruUrjdA1IizYF023huQr0xNHjU1lBwsLw48bSwgePY2kpGHq4p8bsvAxU2lyhZpqVFnalEAOLY2TLIk.0ORuV3G0',
}

headers_following = {
    'accept': '*/*',
    'accept-language': 'en,en-US;q=0.9,ru-RU;q=0.8,ru;q=0.7',
    'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'content-type': 'application/json',
    'priority': 'u=1, i',
    'referer': 'https://x.com/{name_user}/following',
    'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    'sec-ch-ua-arch': '"arm"',
    'sec-ch-ua-bitness': '"64"',
    'sec-ch-ua-full-version': '"139.0.7258.66"',
    'sec-ch-ua-full-version-list': '"Not;A=Brand";v="99.0.0.0", "Google Chrome";v="139.0.7258.66", "Chromium";v="139.0.7258.66"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"macOS"',
    'sec-ch-ua-platform-version': '"15.5.0"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    'x-client-transaction-id': 'tSbOKvUFJt7u94S2wpt5Av4LKsd7th19z7l7+GZO8DM3cV3WGkQXNilHeFVsWX05XOmC5bHr8Cq5l04wZFta3N0ZKjm7tg',
    'x-csrf-token': 'c67939e914a041fc74e33371011472d9d16504b5040be5d9047221ac0ea2ee2a7b7a5f1378ef215321f11e29289877fad9e96ecbc0b3aab084671cbf449adf0e2f12f88a8906eead2ae22696f576b570',
    'x-twitter-active-user': 'yes',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-client-language': 'ru',
    'x-xp-forwarded-for': 'a6f6da8219e2e2cdfb29d98f21590dd9c77148c93ad4fbdc71f89efc63b60feb46d203ee7691326d2fff597fe4a68f91f86087e7a92ca71bc7a28ac45069b479346e235648d555ba193f5e03315c16342cfdce4940ba76f2e54e57602bc11fd6a12ce1938ea4a6decd270e78eca1dd82f1445f93d3745577fd5a566d4770b526c0cd48b7924c62e01235342460481872f9febbc725d0dd246ce9e419f68c87c3e07db6272ffae6799e2979b56002218178ac86e48450e6dfba3359804a5150f29cee7679ce436491fe8b5c7ea7a746083aed49a2b1197641f6a2d2328dfbd75486f007284726b48289c019f631821b6e70059687e855ba83336a5716037a02a469',
    'cookie': 'ok_okg={"_expire":{},"currentMedia":"lg"}; ok_global={"_expire":{}}; ok_default={"_expire":{}}; kdt=tIUH0HtfnnAmHOjGeZ8Vg2sFmIBty0MPcE035SEA; night_mode=2; _monitor_extras={"deviceId":"IHd_l_bj9G0WmWokVdooqa","eventId":7,"sequenceNumber":7}; amp_669cbf=19c36faa-457b-42a5-ae11-f662b20c8ee5.MTljMzZmYWEtNDU3Yi00MmE1LWFlMTEtZjY2MmIyMGM4ZWU1..1i5ghfh2q.1i5ghfh2r.5.0.5; twtr_pixel_opt_in=Y; amp_56bf9d=19c36faa-457b-42a5-ae11-f662b20c8ee5...1i5lo7ltt.1i5lom3r1.1.1.2; d_prefs=MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw; personalization_id="v1_RsvteDXPzLImJVYFKULH/w=="; __cuid=b6ed2207bbb6467fb2d91f43eaf62a91; first_ref=https%3A%2F%2Fx.com%2Fsearch%3Fq%3D%2524hosico%26src%3Drecent_search_click; guest_id_ads=v1%3A175232397208590930; guest_id_marketing=v1%3A175232397208590930; lang=ru; ok_global={"_expire":{}}; ok_default={"_expire":{}}; ads_prefs="HBERAAA="; auth_multi="1527960562235236354:a380486e2a6bfcfd3ce3c38e99c27c1858fe0caa|1823675166096023555:fe44688dff6387dfde0cb99a63a29106e82e28b5"; auth_token=bd079fea2a671c42a6e95e00707198d1779ae867; guest_id=v1%3A175485905244719279; twid=u%3D1538858660801269763; ct0=c67939e914a041fc74e33371011472d9d16504b5040be5d9047221ac0ea2ee2a7b7a5f1378ef215321f11e29289877fad9e96ecbc0b3aab084671cbf449adf0e2f12f88a8906eead2ae22696f576b570; cf_clearance=ReQm3hb53.ShoGFPMT7x52PDxsEb4pLWbRzt7F8n6wk-1754927951-1.2.1.1-mrn6QkHWwyIHungjByaw9E4xzQCy16paFet3DWlTgeDnWSr1_yxClGbdKSlCnhKblnaSV38eXCOINRBmyIbTdURDovYb8UuDVSexlw10kg.CKt9M_y2_MCJMo18gktiurgfIHgKzHVTgb16vPjUzZeY.70ow_5NUm.9sNtQ2RRYjZPE0O7EU7X23h.Hzy4MAa4z6b_60xM3OambobxFz3hSXJdiw_8_22rb7SevodTw; _twitter_sess=BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCO9v25mYAToMY3NyZl9p%250AZCIlNjkyOGI5M2JmNTBkMzQ0MjNkNWYxMGUwZTNhODNmOTY6B2lkIiVmNWZm%250AYzg4MzE4ZGI5Mzg3MGIxMjVhY2VhNTYyMTRjYg%253D%253D--29273ef817f8e65030e5c50daceaca34d6bf6069; ok_okg={"_expire":{},"currentMedia":"xl"}; __cf_bm=5tVovvw3xBVrymBxRt3290aGv75wwqPUPmQcKB_gbM4-1755290244-1.0.1.1-39IXRx1bS1wLhuu0pxjruUrjdA1IizYF023huQr0xNHjU1lBwsLw48bSwgePY2kpGHq4p8bsvAxU2lyhZpqVFnalEAOLY2TLIk.0ORuV3G0',
}

params_following = {
    'variables': '{"userId":"{user_id}","count":20,"includePromotedContent":false}',
    'features': '{"rweb_video_screen_enabled":false,"payments_enabled":false,"rweb_xchat_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"premium_content_api_read_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_grok_analyze_button_fetch_trends_enabled":false,"responsive_web_grok_analyze_post_followups_enabled":true,"responsive_web_jetfuel_frame":true,"responsive_web_grok_share_attachment_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"responsive_web_grok_show_grok_translated_post":false,"responsive_web_grok_analysis_button_from_backend":false,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_grok_image_annotation_enabled":true,"responsive_web_grok_imagine_annotation_enabled":true,"responsive_web_grok_community_note_auto_translation_is_enabled":false,"responsive_web_enhance_cards_enabled":false}',
}


# --- cURL для получениях данных о подписчиках---

cookies_big = {
    'kdt': 'tIUH0HtfnnAmHOjGeZ8Vg2sFmIBty0MPcE035SEA',
    'night_mode': '2',
    '_monitor_extras': '{"deviceId":"IHd_l_bj9G0WmWokVdooqa","eventId":7,"sequenceNumber":7}',
    'amp_669cbf': '19c36faa-457b-42a5-ae11-f662b20c8ee5.MTljMzZmYWEtNDU3Yi00MmE1LWFlMTEtZjY2MmIyMGM4ZWU1..1i5ghfh2q.1i5ghfh2r.5.0.5',
    'twtr_pixel_opt_in': 'Y',
    'amp_56bf9d': '19c36faa-457b-42a5-ae11-f662b20c8ee5...1i5lo7ltt.1i5lom3r1.1.1.2',
    'd_prefs': 'MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw',
    'personalization_id': '"v1_RsvteDXPzLImJVYFKULH/w=="',
    'guest_id_ads': 'v1%3A174724380802786926',
    'guest_id_marketing': 'v1%3A174724380802786926',
    'cf_clearance': '5BVvpIzix7NKCMm.4xf.2CMkEM6s0V9KkCHM1U7ADbk-1750182280-1.2.1.1-1rsRRpEXCSX3mERcZi8bW5GaWFgY_NM3SNtur8ltNRl00fX7UPNt0mCMNRssyr22bRNeZU2M3xZpsFHU8_KU6x.edmyJF3cijNfRWQrSI.9tOFhuK.bqOuSCcUSzRc1HvvaH3TQZQfQQ5laamYtGvFV6DDi6fZ8NlJVYTV22UkRer_ado.Fc3twwmZVxg7l2XFu5AFGnV6DRgFliK6snSF4b3qpCVhJNO5gKUNwJp1NUkXTzuPET5jwggw7MqoDKD_WpXMJBSZ6EcEutwrKYpNN6eatRgy_1bmqqidsQDPiS4RdgDde8K2tmqr1jAfINazD49YOpMdzy.eaSkgXMoVzjjr20EgUtmUwbs7bwUPVNDoGoJmiHiKXu16a8aXoG',
    'first_ref': 'https%3A%2F%2Fwww.google.com%2F',
    'ads_prefs': '"HBERAAA="',
    'auth_multi': '"1527960562235236354:a380486e2a6bfcfd3ce3c38e99c27c1858fe0caa|1823675166096023555:fe44688dff6387dfde0cb99a63a29106e82e28b5"',
    'auth_token': 'bd079fea2a671c42a6e95e00707198d1779ae867',
    'guest_id': 'v1%3A175232397208590930',
    'twid': 'u%3D1538858660801269763',
    'ct0': '431649610ef3afbd43af31e64aeacfdf3967f8b708040eb9f84e0a385cafda096828e14167fa490c0c24324b04e3c7be79f03f54fc28daa1e370ff03df0da492d5a00871e4115177c064a64fbdd83043',
    'lang': 'ru',
    'ok_global': '{"_expire":{}}',
    'ok_default': '{"_expire":{}}',
    '__cf_bm': 'v4wcxcxiLucGBGHB6.PEYUTCSvjLFw9BGKhXIlZRrzo-1752426011-1.0.1.1-NZcn2gHqrT52RhFxf5FabX651t2F73v5i.3RZfNnTzIqLB0X_VGivqg0CWXzdJW7jNdsEkZoi6J5A1_XNdtWtKmzYtopwevFwcvcR9xZJrk',
    'ok_okg': '{"_expire":{},"currentMedia":"md"}',
}

headers_big = {
    'accept': '*/*',
    'accept-language': 'en,en-US;q=0.9,ru-RU;q=0.8,ru;q=0.7',
    'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'content-type': 'application/json',
    'priority': 'u=1, i',
    'referer': 'https://x.com/{username_big}/verified_followers',
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    'sec-ch-ua-arch': '"arm"',
    'sec-ch-ua-bitness': '"64"',
    'sec-ch-ua-full-version': '"138.0.7204.101"',
    'sec-ch-ua-full-version-list': '"Not)A;Brand";v="8.0.0.0", "Chromium";v="138.0.7204.101", "Google Chrome";v="138.0.7204.101"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"macOS"',
    'sec-ch-ua-platform-version': '"15.5.0"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    'x-client-transaction-id': 'wcr9tdRUTMfdfETzlfWWNIG+MeOCfa3ZEgJC82beA1rM7Nb3t/F2At95NfRlmoj3nIdC5cVOaFrkkNDYW6H31qTowxF5wg',
    'x-csrf-token': '431649610ef3afbd43af31e64aeacfdf3967f8b708040eb9f84e0a385cafda096828e14167fa490c0c24324b04e3c7be79f03f54fc28daa1e370ff03df0da492d5a00871e4115177c064a64fbdd83043',
    'x-twitter-active-user': 'yes',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-client-language': 'ru',
    'x-xp-forwarded-for': 'fcae9488ebaffe58f3e4704e304b0c01a7e36684f7c71775131111621eafc6d61f08ac80954251e16450f2ca394f898c5521a397cecbf24a51c25efabf3061345bfc91bdfd11c44ac906e468901e808ef8b9e8de6bca7eb770a53d8ba95268390ea752afb12620a435d52840d346b3c535ef8ea8e2050ab536e227dc3432c5f65fbdff3594a92d1a5280d52014e65c9bad6dfd8cf37e29944576120eee0f28a667826e058c2ee1c0fd4948d63b9a07c936072a24f6f8b86dcf2704e726d8eb87732fe9e6d3dd96a0dd0ecc63f16ab70ba6a6aa892c28bc7f4a2a929f299bfb27c5bd4ffb551632cd0ac629edfff16f6c499868909728cd5273186c894413372bdc',
    'cookie': 'kdt=tIUH0HtfnnAmHOjGeZ8Vg2sFmIBty0MPcE035SEA; night_mode=2; _monitor_extras={"deviceId":"IHd_l_bj9G0WmWokVdooqa","eventId":7,"sequenceNumber":7}; amp_669cbf=19c36faa-457b-42a5-ae11-f662b20c8ee5.MTljMzZmYWEtNDU3Yi00MmE1LWFlMTEtZjY2MmIyMGM4ZWU1..1i5ghfh2q.1i5ghfh2r.5.0.5; twtr_pixel_opt_in=Y; amp_56bf9d=19c36faa-457b-42a5-ae11-f662b20c8ee5...1i5lo7ltt.1i5lom3r1.1.1.2; d_prefs=MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw; personalization_id="v1_RsvteDXPzLImJVYFKULH/w=="; guest_id_ads=v1%3A174724380802786926; guest_id_marketing=v1%3A174724380802786926; cf_clearance=5BVvpIzix7NKCMm.4xf.2CMkEM6s0V9KkCHM1U7ADbk-1750182280-1.2.1.1-1rsRRpEXCSX3mERcZi8bW5GaWFgY_NM3SNtur8ltNRl00fX7UPNt0mCMNRssyr22bRNeZU2M3xZpsFHU8_KU6x.edmyJF3cijNfRWQrSI.9tOFhuK.bqOuSCcUSzRc1HvvaH3TQZQfQQ5laamYtGvFV6DDi6fZ8NlJVYTV22UkRer_ado.Fc3twwmZVxg7l2XFu5AFGnV6DRgFliK6snSF4b3qpCVhJNO5gKUNwJp1NUkXTzuPET5jwggw7MqoDKD_WpXMJBSZ6EcEutwrKYpNN6eatRgy_1bmqqidsQDPiS4RdgDde8K2tmqr1jAfINazD49YOpMdzy.eaSkgXMoVzjjr20EgUtmUwbs7bwUPVNDoGoJmiHiKXu16a8aXoG; first_ref=https%3A%2F%2Fwww.google.com%2F; ads_prefs="HBERAAA="; auth_multi="1527960562235236354:a380486e2a6bfcfd3ce3c38e99c27c1858fe0caa|1823675166096023555:fe44688dff6387dfde0cb99a63a29106e82e28b5"; auth_token=bd079fea2a671c42a6e95e00707198d1779ae867; guest_id=v1%3A175232397208590930; twid=u%3D1538858660801269763; ct0=431649610ef3afbd43af31e64aeacfdf3967f8b708040eb9f84e0a385cafda096828e14167fa490c0c24324b04e3c7be79f03f54fc28daa1e370ff03df0da492d5a00871e4115177c064a64fbdd83043; lang=ru; ok_global={"_expire":{}}; ok_default={"_expire":{}}; __cf_bm=v4wcxcxiLucGBGHB6.PEYUTCSvjLFw9BGKhXIlZRrzo-1752426011-1.0.1.1-NZcn2gHqrT52RhFxf5FabX651t2F73v5i.3RZfNnTzIqLB0X_VGivqg0CWXzdJW7jNdsEkZoi6J5A1_XNdtWtKmzYtopwevFwcvcR9xZJrk; ok_okg={"_expire":{},"currentMedia":"md"}',
}

params_big = {
    'variables': '{"userId":"{user_id_big}","count":20,"includePromotedContent":false}',
    'features': '{"rweb_video_screen_enabled":false,"payments_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"premium_content_api_read_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_grok_analyze_button_fetch_trends_enabled":false,"responsive_web_grok_analyze_post_followups_enabled":true,"responsive_web_jetfuel_frame":true,"responsive_web_grok_share_attachment_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"responsive_web_grok_show_grok_translated_post":false,"responsive_web_grok_analysis_button_from_backend":false,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_grok_image_annotation_enabled":true,"responsive_web_grok_community_note_auto_translation_is_enabled":false,"responsive_web_enhance_cards_enabled":false}',
}

# --- cURL для получения ответов (replies) ---

cookies_reply = {
    'kdt': 'tIUH0HtfnnAmHOjGeZ8Vg2sFmIBty0MPcE035SEA',
    'night_mode': '2',
    '_monitor_extras': '{"deviceId":"IHd_l_bj9G0WmWokVdooqa","eventId":7,"sequenceNumber":7}',
    'amp_669cbf': '19c36faa-457b-42a5-ae11-f662b20c8ee5.MTljMzZmYWEtNDU3Yi00MmE1LWFlMTEtZjY2MmIyMGM4ZWU1..1i5ghfh2q.1i5ghfh2r.5.0.5',
    'twtr_pixel_opt_in': 'Y',
    'amp_56bf9d': '19c36faa-457b-42a5-ae11-f662b20c8ee5...1i5lo7ltt.1i5lom3r1.1.1.2',
    'd_prefs': 'MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw',
    'personalization_id': '"v1_RsvteDXPzLImJVYFKULH/w=="',
    'guest_id_ads': 'v1%3A174724380802786926',
    'guest_id_marketing': 'v1%3A174724380802786926',
    'ads_prefs': '"HBERAAA="',
    'auth_multi': '"1527960562235236354:a380486e2a6bfcfd3ce3c38e99c27c1858fe0caa|1823675166096023555:fe44688dff6387dfde0cb99a63a29106e82e28b5"',
    'auth_token': 'bd079fea2a671c42a6e95e00707198d1779ae867',
    'guest_id': 'v1%3A175232397208590930',
    'twid': 'u%3D1538858660801269763',
    'ct0': '431649610ef3afbd43af31e64aeacfdf3967f8b708040eb9f84e0a385cafda096828e14167fa490c0c24324b04e3c7be79f03f54fc28daa1e370ff03df0da492d5a00871e4115177c064a64fbdd83043',
    '__cuid': 'b6ed2207bbb6467fb2d91f43eaf62a91',
    'cf_clearance': '1wBvumQu7e7SSLRoGOvlu_Gka9lx_mMOOFYO0uIL1lQ-1753917182-1.2.1.1-PQ0GkxYrGC9AQVsbHYAqdBfXVd3i2nDtDssnnkVmD5wShtm4J9wN9m3aM5rTVgrV2kZYe1f.sQhwmPLuJp3OdquYVtsSpfxPr4e0HvSC63NXI9bv0gofkJxj2KW1UBCJfQIsrGB4I0hMZk_AjnCXz89NFdnjq2GI_97n5rB7NMYt4ycP3XoGojCmURwOnSLAxGIsKmDXVkYc9tb5ohij8mwXx.1qsbR5JjqNoIn19XE',
    'lang': 'ru',
    'ok_global': '{"_expire":{}}',
    'ok_default': '{"_expire":{}}',
    'first_ref': 'https%3A%2F%2Fx.com%2Fsearch%3Fq%3D%2524hosico%26src%3Drecent_search_click',
    '__cf_bm': 'FjjJNXDd.PSr3neZnlJ2zf79vYNHVkm91Grxe23BWWs-1754565050-1.0.1.1-nsMz0EhP8zeTv80pyY3Qwy7dlOuFFI6c4CO9lvcDg0YbrKtkMj1NcwcRtZBmv.2juDU2tS_bYxyybu.RaG5JZ217k9ZcAqkJ5gbB6s_N97I',
    'ok_okg': '{"_expire":{},"currentMedia":"lg"}',
}

headers_reply = {
    'accept': '*/*',
    'accept-language': 'en,en-US;q=0.9,ru-RU;q=0.8,ru;q=0.7',
    'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'content-type': 'application/json',
    'priority': 'u=1, i',
    'referer': 'https://x.com/{username}/with_replies',
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    'sec-ch-ua-arch': '"arm"',
    'sec-ch-ua-bitness': '"64"',
    'sec-ch-ua-full-version': '"138.0.7204.184"',
    'sec-ch-ua-full-version-list': '"Not)A;Brand";v="8.0.0.0", "Chromium";v="138.0.7204.184", "Google Chrome";v="138.0.7204.184"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"macOS"',
    'sec-ch-ua-platform-version': '"15.5.0"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    'x-client-transaction-id': 'FjWsY1ep/j3NUQOrMtNyF/U8uZ3SZadddE9tGBC61Q+ZErqge3DCjmc3e4uESLq5Jos+UxLQVWiEdO9CnF91djnhzv3DFQ',
    'x-csrf-token': '431649610ef3afbd43af31e64aeacfdf3967f8b708040eb9f84e0a385cafda096828e14167fa490c0c24324b04e3c7be79f03f54fc28daa1e370ff03df0da492d5a00871e4115177c064a64fbdd83043',
    'x-twitter-active-user': 'yes',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-client-language': 'ru',
    'x-xp-forwarded-for': '870c1c95a9c6c07a18d12e78ce2605568ad290cbbf7a537e753a15058224b86b5426e78af2fee6b13713cb03ff52365614e11923dd33ab489bfbf992defb16e4d6e343a3a0c259076b78d61297d38c79a691e1e99a4309dfdd1b538ef17463a90fa9841ea38c8fd449a8e7b89d898ebb558f998f6a1bafb76d8d8cfdb1c4da8a6f3bd7ca28b9e1e3b4bb169dcbaa30064d3fbe12dd1ff12b11eb7960dac27fa495c3da62d4928f111c3956e5299f1553c8837ef5209e2884b6e6f39d59936ee430a9edfd5b471e594b352904062b2a2de131ebdc75d316e077bca586b9dc34e74726c6e18dfc4ed1a92670b868d7ad857058a394bb07fa4a60e30bcd8b38a1d7b5',
}

params_reply = {
    'variables': '{"userId":"{user_id}","count":20,"includePromotedContent":true,"withCommunity":true,"withVoice":true}',
    'features': '{"rweb_video_screen_enabled":false,"payments_enabled":false,"rweb_xchat_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"premium_content_api_read_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_grok_analyze_button_fetch_trends_enabled":false,"responsive_web_grok_analyze_post_followups_enabled":true,"responsive_web_jetfuel_frame":true,"responsive_web_grok_share_attachment_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"responsive_web_grok_show_grok_translated_post":false,"responsive_web_grok_analysis_button_from_backend":false,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_grok_image_annotation_enabled":true,"responsive_web_grok_community_note_auto_translation_is_enabled":false,"responsive_web_enhance_cards_enabled":false}',
    'fieldToggles': '{"withArticlePlainText":false}',
}

# --- cURL для получения последних постов/репостов (info) ---
cookies_info = {
    'ok_okg': '{"_expire":{},"currentMedia":"lg"}',
    'ok_global': '{"_expire":{}}',
    'ok_default': '{"_expire":{}}',
    'kdt': 'tIUH0HtfnnAmHOjGeZ8Vg2sFmIBty0MPcE035SEA',
    'night_mode': '2',
    '_monitor_extras': '{"deviceId":"IHd_l_bj9G0WmWokVdooqa","eventId":7,"sequenceNumber":7}',
    'amp_669cbf': '19c36faa-457b-42a5-ae11-f662b20c8ee5.MTljMzZmYWEtNDU3Yi00MmE1LWFlMTEtZjY2MmIyMGM4ZWU1..1i5ghfh2q.1i5ghfh2r.5.0.5',
    'twtr_pixel_opt_in': 'Y',
    'amp_56bf9d': '19c36faa-457b-42a5-ae11-f662b20c8ee5...1i5lo7ltt.1i5lom3r1.1.1.2',
    'd_prefs': 'MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw',
    'personalization_id': '"v1_RsvteDXPzLImJVYFKULH/w=="',
    '__cuid': 'b6ed2207bbb6467fb2d91f43eaf62a91',
    'first_ref': 'https%3A%2F%2Fx.com%2Fsearch%3Fq%3D%2524hosico%26src%3Drecent_search_click',
    'guest_id_ads': 'v1%3A175232397208590930',
    'guest_id_marketing': 'v1%3A175232397208590930',
    'lang': 'ru',
    'ok_global': '{"_expire":{}}',
    'ok_default': '{"_expire":{}}',
    'ads_prefs': '"HBERAAA="',
    'auth_multi': '"1527960562235236354:a380486e2a6bfcfd3ce3c38e99c27c1858fe0caa|1823675166096023555:fe44688dff6387dfde0cb99a63a29106e82e28b5"',
    'auth_token': 'bd079fea2a671c42a6e95e00707198d1779ae867',
    'guest_id': 'v1%3A175485905244719279',
    'twid': 'u%3D1538858660801269763',
    'ct0': 'c67939e914a041fc74e33371011472d9d16504b5040be5d9047221ac0ea2ee2a7b7a5f1378ef215321f11e29289877fad9e96ecbc0b3aab084671cbf449adf0e2f12f88a8906eead2ae22696f576b570',
    'cf_clearance': 'ReQm3hb53.ShoGFPMT7x52PDxsEb4pLWbRzt7F8n6wk-1754927951-1.2.1.1-mrn6QkHWwyIHungjByaw9E4xzQCy16paFet3DWlTgeDnWSr1_yxClGbdKSlCnhKblnaSV38eXCOINRBmyIbTdURDovYb8UuDVSexlw10kg.CKt9M_y2_MCJMo18gktiurgfIHgKzHVTgb16vPjUzZeY.70ow_5NUm.9sNtQ2RRYjZPE0O7EU7X23h.Hzy4MAa4z6b_60xM3OambobxFz3hSXJdiw_8_22rb7SevodTw',
    '_twitter_sess': 'BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCO9v25mYAToMY3NyZl9p%250AZCIlNjkyOGI5M2JmNTBkMzQ0MjNkNWYxMGUwZTNhODNmOTY6B2lkIiVmNWZm%250AYzg4MzE4ZGI5Mzg3MGIxMjVhY2VhNTYyMTRjYg%253D%253D--29273ef817f8e65030e5c50daceaca34d6bf6069',
    'ok_okg': '{"_expire":{},"currentMedia":"xl"}',
    '__cf_bm': '5tVovvw3xBVrymBxRt3290aGv75wwqPUPmQcKB_gbM4-1755290244-1.0.1.1-39IXRx1bS1wLhuu0pxjruUrjdA1IizYF023huQr0xNHjU1lBwsLw48bSwgePY2kpGHq4p8bsvAxU2lyhZpqVFnalEAOLY2TLIk.0ORuV3G0',
}

headers_info = {
    'accept': '*/*',
    'accept-language': 'en,en-US;q=0.9,ru-RU;q=0.8,ru;q=0.7',
    'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'content-type': 'application/json',
    'priority': 'u=1, i',
    'referer': 'https://x.com/{username}',
    'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    'sec-ch-ua-arch': '"arm"',
    'sec-ch-ua-bitness': '"64"',
    'sec-ch-ua-full-version': '"139.0.7258.66"',
    'sec-ch-ua-full-version-list': '"Not;A=Brand";v="99.0.0.0", "Google Chrome";v="139.0.7258.66", "Chromium";v="139.0.7258.66"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"macOS"',
    'sec-ch-ua-platform-version': '"15.5.0"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    'x-client-transaction-id': 'WN0nHFlP2quPrUAYOznFveYwVXkTbm4kpygooVrVmBYVSg3sI8QnMSZOQNzvFLmZT9QrFlxXU33E4ujGRSikmNypELpvWw',
    'x-csrf-token': 'c67939e914a041fc74e33371011472d9d16504b5040be5d9047221ac0ea2ee2a7b7a5f1378ef215321f11e29289877fad9e96ecbc0b3aab084671cbf449adf0e2f12f88a8906eead2ae22696f576b570',
    'x-twitter-active-user': 'yes',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-client-language': 'ru',
    'x-xp-forwarded-for': '3a997092707c6f8616dad385d0ebbed1462da56a5faef96e19e771e7bb1aac020e65a778195ffb10b4826a97af2e3e146768a6a8b8c8bfb8c912d91c3595a7bba2d587379faee57e3e8695100613f678b612c109267ad1013237fe8892c51e6a08747e335fcd12eda7b237357957f6e571b757937e0ac03f36717d63685ecab6d3557f97d9a3f551fa6f45b6c565567a9eb60447c5678c96614533ab58db3e5a29e1ff143e0bb6d8ca73b1642343c0928365729805aee7dde6637c423c2606df2d97f1e007f3ac26022d9d646bea900e609fe45c97ce34e104891eabefd5ea8b1e221dfb396c49a8609f0edeb096686bfde64e623ff438405d685c9739970a354f',
    'cookie': 'ok_okg={"_expire":{},"currentMedia":"lg"}; ok_global={"_expire":{}}; ok_default={"_expire":{}}; kdt=tIUH0HtfnnAmHOjGeZ8Vg2sFmIBty0MPcE035SEA; night_mode=2; _monitor_extras={"deviceId":"IHd_l_bj9G0WmWokVdooqa","eventId":7,"sequenceNumber":7}; amp_669cbf=19c36faa-457b-42a5-ae11-f662b20c8ee5.MTljMzZmYWEtNDU3Yi00MmE1LWFlMTEtZjY2MmIyMGM4ZWU1..1i5ghfh2q.1i5ghfh2r.5.0.5; twtr_pixel_opt_in=Y; amp_56bf9d=19c36faa-457b-42a5-ae11-f662b20c8ee5...1i5lo7ltt.1i5lom3r1.1.1.2; d_prefs=MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw; personalization_id="v1_RsvteDXPzLImJVYFKULH/w=="; __cuid=b6ed2207bbb6467fb2d91f43eaf62a91; first_ref=https%3A%2F%2Fx.com%2Fsearch%3Fq%3D%2524hosico%26src%3Drecent_search_click; guest_id_ads=v1%3A175232397208590930; guest_id_marketing=v1%3A175232397208590930; lang=ru; ok_global={"_expire":{}}; ok_default={"_expire":{}}; ads_prefs="HBERAAA="; auth_multi="1527960562235236354:a380486e2a6bfcfd3ce3c38e99c27c1858fe0caa|1823675166096023555:fe44688dff6387dfde0cb99a63a29106e82e28b5"; auth_token=bd079fea2a671c42a6e95e00707198d1779ae867; guest_id=v1%3A175485905244719279; twid=u%3D1538858660801269763; ct0=c67939e914a041fc74e33371011472d9d16504b5040be5d9047221ac0ea2ee2a7b7a5f1378ef215321f11e29289877fad9e96ecbc0b3aab084671cbf449adf0e2f12f88a8906eead2ae22696f576b570; cf_clearance=ReQm3hb53.ShoGFPMT7x52PDxsEb4pLWbRzt7F8n6wk-1754927951-1.2.1.1-mrn6QkHWwyIHungjByaw9E4xzQCy16paFet3DWlTgeDnWSr1_yxClGbdKSlCnhKblnaSV38eXCOINRBmyIbTdURDovYb8UuDVSexlw10kg.CKt9M_y2_MCJMo18gktiurgfIHgKzHVTgb16vPjUzZeY.70ow_5NUm.9sNtQ2RRYjZPE0O7EU7X23h.Hzy4MAa4z6b_60xM3OambobxFz3hSXJdiw_8_22rb7SevodTw; _twitter_sess=BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCO9v25mYAToMY3NyZl9p%250AZCIlNjkyOGI5M2JmNTBkMzQ0MjNkNWYxMGUwZTNhODNmOTY6B2lkIiVmNWZm%250AYzg4MzE4ZGI5Mzg3MGIxMjVhY2VhNTYyMTRjYg%253D%253D--29273ef817f8e65030e5c50daceaca34d6bf6069; ok_okg={"_expire":{},"currentMedia":"xl"}',
}

params_info = {
    'variables': '{"userId":"{user_id}","count":20,"includePromotedContent":true,"withQuickPromoteEligibilityTweetFields":true,"withVoice":true}',
    'features': '{"rweb_video_screen_enabled":false,"payments_enabled":false,"rweb_xchat_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"premium_content_api_read_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_grok_analyze_button_fetch_trends_enabled":false,"responsive_web_grok_analyze_post_followups_enabled":true,"responsive_web_jetfuel_frame":true,"responsive_web_grok_share_attachment_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"responsive_web_grok_show_grok_translated_post":false,"responsive_web_grok_analysis_button_from_backend":false,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_grok_image_annotation_enabled":true,"responsive_web_grok_imagine_annotation_enabled":true,"responsive_web_grok_community_note_auto_translation_is_enabled":false,"responsive_web_enhance_cards_enabled":false}',
    'fieldToggles': '{"withArticlePlainText":false}',
}

bot_ready = False  # Флаг готовности бота

# =============================================================================
# 🕐 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def convert_twitter_time_to_discord_timestamp(twitter_time_str):
    """Преобразует twitter time в discord timestamp"""
    if not twitter_time_str:
        return ""
    try:
        dt = datetime.strptime(twitter_time_str, "%a %b %d %H:%M:%S %z %Y")
        unix_timestamp = int(dt.timestamp())
        return f"<t:{unix_timestamp}:F>"
    except Exception as e:
        logger.error(f"Ошибка конвертации времени: {e}")
        return twitter_time_str

def is_panel_channel(channel_id: int) -> bool:
    return channel_id == CONTROL_PANEL_CHANNEL_ID

# =============================================================================
# 🎮 DISCORD EVENTS И SLASH-КОМАНДЫ
# =============================================================================
@tree.command(name="clear", description="Очистить все сообщения в основном канале")
async def clear_main_channel(interaction: discord.Interaction):
    try:
        # Проверяем права пользователя
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ У вас нет прав для удаления сообщений!", ephemeral=True)
            return
        
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message("❌ Основной канал не найден!", ephemeral=True)
            return
        
        await interaction.response.send_message("🧹 Начинаю очистку канала...", ephemeral=True)
        
        # Удаляем сообщения по 100 штук (лимит Discord API)
        deleted_count = 0
        async for message in channel.history(limit=None):
            try:
                await message.delete()
                deleted_count += 1
                if deleted_count % 10 == 0:  # Обновляем каждые 10 удалений
                    await interaction.edit_original_response(content=f"🧹 Удалено сообщений: {deleted_count}")
                await asyncio.sleep(0.5)  # Задержка чтобы не превысить лимиты Discord
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения: {e}")
                continue
        
        await interaction.edit_original_response(content=f"✅ Очистка завершена! Удалено сообщений: {deleted_count}")
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Ошибка при очистке канала: {e}", ephemeral=True)

async def ensure_single_reply_panel(channel):
    last_panel = None
    async for msg in channel.history(limit=50):
        if msg.author == bot.user and msg.embeds and any('Reply Channels' in (e.title or '') for e in msg.embeds):
            last_panel = msg
            break
    embed = discord.Embed(
        title="Reply Channels",
        description=(
            "Create/Delete - создать или удалить канал в категории x2-replies\n"
            "Можно отслеживать таргеты в соотвествии с вашей категории\n"
        ),
        color=0x2ecc71
    )
    if last_panel:
        await last_panel.edit(embed=embed, view=ReplyChannelView())
    else:
        await channel.send(embed=embed, view=ReplyChannelView())

# --- Embed с кнопками create/delete для info ---
class InfoChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Info Channel", style=discord.ButtonStyle.primary, custom_id="create_info_channel")
    async def create_info_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message("❌ Ошибка: не удалось получить информацию о сервере", ephemeral=True)
                return

            # Модалка для ввода имени канала (по аналогии с reply)
            class InfoChannelNameModal(discord.ui.Modal, title="Создание Info канала"):
                def __init__(self):
                    super().__init__()
                    self.channel_name = discord.ui.TextInput(
                        label="Имя канала",
                        placeholder="Введите имя для нового info-канала",
                        min_length=1,
                        max_length=32,
                        required=True,
                        custom_id="info_channel_name_input"
                    )
                    self.add_item(self.channel_name)

                async def on_submit(self, modal_interaction: discord.Interaction):
                    name = self.channel_name.value.strip()
                    # Санитизация имени
                    name = name.replace(" ", "-").replace("_", "-")
                    name = "".join(c for c in name if c.isalnum() or c == "-")
                    if not name:
                        await modal_interaction.response.send_message("❌ Некорректное имя канала", ephemeral=True)
                        return
                    # Просто используем имя как есть
                    # Категория для info-каналов
                    category = discord.utils.get(guild.categories, id=1404511212246401185)
                    if not category:
                        category = await guild.create_category("info")
                    # Проверка на существование
                    existing = discord.utils.get(category.channels, name=name)
                    if existing:
                        await modal_interaction.response.send_message(f"❌ Канал #{name} уже существует", ephemeral=True)
                        return
                    ch = await guild.create_text_channel(name, category=category)
                    # Инициализируем хранилище для этого канала (жёстко, как в reply)
                    try:
                        ensure_info_storage_exists()
                        try:
                            with open(INFO_CHANNELS_FILE, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            data[str(ch.id)] = []
                            with open(INFO_CHANNELS_FILE, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            logger.debug(f"Инициализирован {INFO_CHANNELS_FILE} для канала {ch.id}")
                        except Exception as e:
                            logger.error(f"Ошибка при инициализации {INFO_CHANNELS_FILE}: {e}")
                        
                        # Инициализируем txt-файл со списком пользователей (по аналогии с reply)
                        txt_path = os.path.join(DATA_DIR_INFO, f"info_{ch.id}.txt")
                        try:
                            with open(txt_path, 'w', encoding='utf-8') as f:
                                f.write("# Список пользователей для отслеживания info\n")
                                f.write("# Каждый пользователь на новой строке\n")
                            logger.debug(f"Создан файл {txt_path}")
                        except Exception as e:
                            logger.error(f"Ошибка при создании файла {txt_path}: {e}")
                        
                        # Инициализируем хранилище для этого канала
                        save_info_targets_for_channel(ch.id, [])
                        
                        # Логируем создание файлов
                        logger.success(f"Создан info-канал: {ch.name} (ID: {ch.id})")
                        logger.success(f"Создан txt-файл: {txt_path}")
                        logger.success(f"Инициализировано хранилище для канала {ch.id}")
                        
                        # --- ДОБАВИТЬ (по аналогии с reply_channels) ---
                        # Обновляем справочник info-каналов с метаданными
                        channels_meta_path = os.path.join(DATA_DIR_INFO, "info_channels.json")
                        try:
                            if os.path.exists(channels_meta_path):
                                try:
                                    with open(channels_meta_path, 'r', encoding='utf-8') as f:
                                        channels_meta = json.load(f)
                                except Exception as e:
                                    logger.error(f"Ошибка при чтении {channels_meta_path}: {e}")
                                    channels_meta = {}
                            else:
                                channels_meta = {}
                            channels_meta[str(ch.id)] = {
                                "id": str(ch.id),
                                "name": ch.name,
                                "created_at": datetime.now().isoformat()
                            }
                            try:
                                with open(channels_meta_path, 'w', encoding='utf-8') as f:
                                    json.dump(channels_meta, f, ensure_ascii=False, indent=2)
                                logger.success(f"Обновлен info_channels.json для канала {ch.id}")
                            except Exception as e:
                                logger.error(f"Ошибка при записи {channels_meta_path}: {e}")
                        except Exception as e:
                            logger.error(f"Ошибка при обновлении info_channels.json: {e}")
                        # --- КОНЕЦ ДОБАВЛЕНИЯ ---
                        
                    except Exception as e:
                        logger.error(f"Ошибка при инициализации хранилища info: {e}")
                    await modal_interaction.response.send_message(
                        f"✅ **Канал создан успешно!**\n\n"
                        f"**Имя:** #{ch.name}\n"
                        f"**Категория:** {category.name}\n"
                        f"**ID:** {ch.id}",
                        ephemeral=True
                    )

            await interaction.response.send_modal(InfoChannelNameModal())
        except Exception as e:
            try:
                await interaction.response.send_message(f"❌ Ошибка создания info-канала: {e}", ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="Delete Info Channel", style=discord.ButtonStyle.danger, custom_id="delete_info_channel")
    async def delete_info_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message("❌ Ошибка: не удалось получить информацию о сервере", ephemeral=True)
                return
            # Получаем каналы в категории info
            category = discord.utils.get(guild.categories, id=1404511212246401185)
            if not category:
                await interaction.response.send_message("❌ Категория info не найдена", ephemeral=True)
                return
            options = []
            for ch in category.channels:
                if isinstance(ch, discord.TextChannel):
                    options.append(discord.SelectOption(label=f"#{ch.name}", value=str(ch.id), description=f"Канал {ch.name}"))
            if not options:
                await interaction.response.send_message("❌ Нет текстовых каналов для удаления", ephemeral=True)
                return
            select = discord.ui.Select(
                placeholder="Выберите info-канал для удаления",
                options=options[:25],
                custom_id="delete_info_channel_select"
            )
            async def select_cb(sel_interaction: discord.Interaction):
                try:
                    ch_id = int(sel_interaction.data["values"][0])
                    ch = guild.get_channel(ch_id)
                    if not ch:
                        await sel_interaction.response.send_message("❌ Канал не найден", ephemeral=True)
                        return
                    confirm_view = ConfirmDeleteInfoView(ch)
                    await sel_interaction.response.send_message(
                        f"⚠️ Подтвердите удаление канала #{ch.name}",
                        view=confirm_view,
                        ephemeral=True
                    )
                except Exception as e:
                    await sel_interaction.response.send_message(f"❌ Ошибка при выборе канала: {e}", ephemeral=True)
            select.callback = select_cb
            view = discord.ui.View()
            view.add_item(select)
            await interaction.response.send_message("Выберите канал для удаления:", view=view, ephemeral=True)
        except Exception as e:
            try:
                await interaction.response.send_message(f"❌ Ошибка удаления info-канала: {e}", ephemeral=True)
            except Exception:
                pass

async def ensure_info_panel_posted():
    channel = bot.get_channel(INFO_PANEL_CHANNEL_ID)
    if not channel:
        logger.error("Канал для info-панели не найден!")
        return
    last_panel = None
    async for msg in channel.history(limit=50):
        if msg.author == bot.user and msg.embeds and any('Info Channels' in (e.title or '') for e in msg.embeds):
            last_panel = msg
            break
    embed = discord.Embed(
        title="Info Channels",
        description=(
            "Create/Delete — создать или удалить канал в категории info\n"
            "Можно отслеживать таргеты в отдельном info-канале\n"
        ),
        color=0x3498db
    )
    if last_panel:
        await last_panel.edit(embed=embed, view=InfoChannelView())
    else:
        await channel.send(embed=embed, view=InfoChannelView())

# =============================================================================
# 📋 SLASH-КОМАНДЫ ДЛЯ INFO (должны быть определены до on_ready)
# =============================================================================

@tree.command(name="list_info", description="Показать отслеживаемых пользователей для этого info-канала")
async def list_info_slash(interaction: discord.Interaction):
    # Проверяем, что канал находится в категории info по названию
    if not interaction.channel or not interaction.channel.category or interaction.channel.category.name != "info":
        await interaction.response.send_message("❌ Команда доступна только в каналах категории INFO", ephemeral=True)
        return
    
    logger.debug(f"list_info: выполняется в канале {interaction.channel.name} (ID: {interaction.channel.id})")
    channel_id = interaction.channel_id
    targets = load_info_targets_for_channel(channel_id)
    if not targets:
        embed = discord.Embed(title="📝 Список для отслеживания info", description="Список пуст", color=0x808080)
    else:
        embed = discord.Embed(title=f"📝 Список для отслеживания info – {len(targets)}", description="\n".join(f"@{t}" for t in targets), color=0x00BFFF)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="add_info", description="Добавить пользователя для отслеживания в этом info-канале")
@app_commands.describe(username="Ник пользователя (без @)")
async def add_info_slash(interaction: discord.Interaction, username: str):
    # Проверяем, что канал находится в категории info по названию
    if not interaction.channel or not interaction.channel.category or interaction.channel.category.name != "info":
        await interaction.response.send_message("❌ Команда доступна только в каналах категории INFO", ephemeral=True)
        return
    
    logger.debug(f"add_info: выполняется в канале {interaction.channel.name} (ID: {interaction.channel.id})")
    channel_id = interaction.channel_id
    targets = load_info_targets_for_channel(channel_id)
    username = username.lstrip('@').strip()
    if username in targets:
        await interaction.response.send_message(f"{username} уже есть в списке", ephemeral=True)
        return
    targets.append(username)
    save_info_targets_for_channel(channel_id, targets)
    await interaction.response.send_message(
        f"{username} добавлен для отслеживания\n"
        f"last_info/info_{channel_id}.txt обновлён",
        ephemeral=True
    )

@tree.command(name="remove_info", description="Удалить пользователя из списка для отслеживания в этом info-канале")
@app_commands.describe(username="Ник пользователя (без @)")
async def remove_info_slash(interaction: discord.Interaction, username: str):
    # Проверяем, что канал находится в категории info по названию
    if not interaction.channel or not interaction.channel.category or interaction.channel.category.name != "info":
        await interaction.response.send_message("❌ Команда доступна только в каналах категории INFO", ephemeral=True)
        return
    
    logger.debug(f"remove_info: выполняется в канале {interaction.channel.name} (ID: {interaction.channel.id})")
    channel_id = interaction.channel_id
    targets = load_info_targets_for_channel(channel_id)
    username = username.lstrip('@').strip()
    if username not in targets:
        await interaction.response.send_message(f"❌ {username} не найден в списке", ephemeral=True)
        return
    targets.remove(username)
    save_info_targets_for_channel(channel_id, targets)
    await interaction.response.send_message(f"✅ {username} удалён из списка для отслеживания", ephemeral=True)

@tree.command(name="sync_info", description="Принудительная синхронизация info-команд")
async def sync_info_slash(interaction: discord.Interaction):
    # Проверяем, что канал находится в категории info по названию
    if not interaction.channel or not interaction.channel.category or interaction.channel.category.name != "info":
        await interaction.response.send_message("❌ Команда доступна только в каналах категории INFO", ephemeral=True)
        return
    
    logger.debug(f"sync_info: выполняется в канале {interaction.channel.name} (ID: {interaction.channel.id})")
    
    try:
        # Принудительная синхронизация команд
        await tree.sync()
        logger.success("Команды info синхронизированы принудительно")
        
        embed = discord.Embed(
            title="🔄 Синхронизация Info-команд",
            description="Команды info успешно синхронизированы с Discord!",
            color=0x00FF00
        )
        embed.add_field(
            name="📋 Доступные команды",
            value="• `/list_info` - показать список таргетов\n• `/add_info` - добавить таргет\n• `/remove_info` - удалить таргет\n• `/status_info` - статус канала",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}")
        await interaction.response.send_message(f"❌ Ошибка при синхронизации: {e}", ephemeral=True)

@tree.command(name="status_info", description="Показать статус info-канала")
async def status_info_slash(interaction: discord.Interaction):
    # Проверяем, что канал находится в категории info по названию
    if not interaction.channel or not interaction.channel.category or interaction.channel.category.name != "info":
        await interaction.response.send_message("❌ Команда доступна только в каналах категории INFO", ephemeral=True)
        return
    
    logger.debug(f"status_info: выполняется в канале {interaction.channel.name} (ID: {interaction.channel.id})")
    
    channel_id = interaction.channel_id
    txt_path = os.path.join(DATA_DIR_INFO, f"info_{channel_id}.txt")
    
    # Проверяем файлы
    txt_exists = os.path.exists(txt_path)
    targets = load_info_targets_for_channel(channel_id)
    
    embed = discord.Embed(
        title="📊 Статус Info-канала",
        description=f"**Канал:** #{interaction.channel.name}\n**ID:** {channel_id}",
        color=0x00BFFF
    )
    
    embed.add_field(
        name="📁 Файлы",
        value=f"**txt-файл:** {'Существует' if txt_exists else 'Не найден'}\n**Путь:** `{txt_path}`",
        inline=False
    )
    
    embed.add_field(
        name="👥 Таргеты",
        value=f"**Количество:** {len(targets)}\n**Список:** {', '.join(f'@{t}' for t in targets) if targets else 'Пусто'}",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# =============================================================================

@bot.event
async def on_disconnect():
    """Логирование при отключении бота (Telegram модуль удален)"""
    try:
        logger.success("📊 Бот отключен - логи сохранены в файл")
    except Exception as e:
        print(f"❌ Ошибка при логировании отключения: {e}")

@bot.event
async def on_ready():
    global bot_ready
    bot_ready = True
    
    logger.success("✅ Discord бот готов к работе")
    
    logger.success(f"Бот запущен как {bot.user}")
    # Готовим хранилище для info при запуске
    # Папка last_info уже создается в начале файла (строки 78-82)
    # try:
    #     ensure_info_storage_exists()
    # except Exception:
    #     pass
    # [REPLY_PANEL] Панель для reply-канала
    try:
        channel = bot.get_channel(CONTROL_PANEL_CHANNEL_ID)
        if channel:
            await ensure_single_reply_panel(channel)
            logger.success(f"Панель управления ReplyChannelView обновлена в канале {CONTROL_PANEL_CHANNEL_ID}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении панели управления: {e}")
    # [INFO_PANEL] Панель для info-канала
    try:
        info_channel = bot.get_channel(INFO_PANEL_CHANNEL_ID)
        if info_channel:
            await ensure_info_panel_posted()
            logger.success(f"Панель управления InfoChannelView обновлена в канале {INFO_PANEL_CHANNEL_ID}")
            logger.success(f"Панель управления InfoChannelView обновлена в канале {INFO_PANEL_CHANNEL_ID}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении info-панели: {e}")
    logger.success(f"Discord бот запущен! Пользователь: {bot.user}")
    logger.info(f"Бот подключен к серверам: {[guild.name for guild in bot.guilds]}")
    try:
        synced = await tree.sync()
        logger.success(f"Слэш-команды синхронизированы: {len(synced)}")
    except Exception as e:
        logger.error(f"Ошибка синхронизации слэш-команд: {e}")
    try:
        bot.add_view(InfoChannelView())
        bot.add_view(ReplyChannelView())
        # Регистрируем ConfirmDeleteView для reply-каналов
        bot.add_view(ConfirmDeleteView(None))  # None будет заменен при создании экземпляра
        logger.success("Persistent views зарегистрированы: InfoChannelView, ReplyChannelView, ConfirmDeleteView")
    except Exception as e:
        logger.error(f"Ошибка при регистрации persistent views: {e}")
    
    # =============================================================================
    # 🔴 TELEGRAM МОДУЛЬ: ОТПРАВКА СТАТУСА ЗАПУСКА
    # =============================================================================
    
    # Статус запуска (Telegram модуль удален)
    logger.info("🚀 Discord бот запущен и готов к работе")
    startup_message = f"🚀 <b>Discord бот запущен и готов к работе</b>\n\n"
    startup_message += f"👤 Пользователь: {bot.user}\n"
    startup_message += f"🏠 Серверы: {len(bot.guilds)}\n"
    startup_message += f"📅 Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    startup_message += f"✅ Модуль info активирован\n"
    startup_message += f"📊 Логи будут отправляться только в файл\n"
    startup_message += f"🔗 Общий канал: bitcoin-eco (только Discord)"
    
    logger.success("✅ Статус запуска отправлен в Discord")
    
    # Telegram модуль удален - приветственное сообщение не отправляется

@tree.command(name="scan", description="Начните сканирование...")
async def start_scan(interaction: discord.Interaction):
    if is_panel_channel(interaction.channel_id):
        await interaction.response.send_message("Команды отключены в панели", ephemeral=True)
        return
    try:
        await scan()
        await interaction.followup.send("✅ Сканирование завершено!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Ошибка при сканировании: {e}", ephemeral=True)

@tree.command(name="add", description="Добавить пользователя в список целей для текущего канала")
@app_commands.describe(username="Ник пользователя (без @)")
async def add_target_slash(interaction: discord.Interaction, username: str):
    if is_panel_channel(interaction.channel_id):
        await interaction.response.send_message("Команды отключены в панели", ephemeral=True)
        return
    # Валидация username
    is_valid, result = validate_username(username)
    if not is_valid:
        await interaction.response.send_message(f"❌ {result}", ephemeral=True)
        return
    username = result  # result содержит очищенный username
    channel_id = interaction.channel_id
    targets = load_targets_for_channel(channel_id)
    if username in targets:
        await interaction.response.send_message(f"{username} уже есть в списке для этого канала", ephemeral=True)
        return
    targets.append(username)
    save_targets_for_channel(channel_id, targets)
    await interaction.response.send_message(f"✅ {username} добавлен в список для канала. Всего: {len(targets)}", ephemeral=True)

@tree.command(name="remove", description="Удалить пользователя из списка целей для текущего канала")
@app_commands.describe(username="Ник пользователя (без @)")
async def remove_target_slash(interaction: discord.Interaction, username: str):
    if is_panel_channel(interaction.channel_id):
        await interaction.response.send_message("Команды отключены в панели", ephemeral=True)
        return
    # Валидация username
    is_valid, result = validate_username(username)
    if not is_valid:
        await interaction.response.send_message(f"❌ {result}", ephemeral=True)
        return
    
    username = result  # result содержит очищенный username
    
    channel_id = interaction.channel_id
    targets = load_targets_for_channel(channel_id)
    if username not in targets:
        await interaction.response.send_message(f"❌ {username} не найден в списке для этого канала", ephemeral=True)
        return
    targets.remove(username)
    save_targets_for_channel(channel_id, targets)
    await interaction.response.send_message(f"✅ {username} удалён из списка для канала. Осталось: {len(targets)}", ephemeral=True)

@tree.command(name="list", description="Показать текущий список целей для канала")
async def list_target_slash(interaction: discord.Interaction):
    if is_panel_channel(interaction.channel_id):
        await interaction.response.send_message("Команды отключены в панели", ephemeral=True)
        return
    channel_id = interaction.channel_id
    targets = load_targets_for_channel(channel_id)
    if not targets:
        await interaction.response.send_message("Список пуст для этого канала", ephemeral=True)
        return
    embed = discord.Embed(
        title=f"Список таргетов для канала – {len(targets)}",
        description="\n".join(f"{t}" for t in targets),
        color=0xFF9800
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Команда /logs удалена - Telegram модуль отключен

@tree.command(name="help", description="Показать справку по командам")
async def help_command_slash(interaction: discord.Interaction):
    if is_panel_channel(interaction.channel_id):
        await interaction.response.send_message("Команды отключены в панели", ephemeral=True)
        return
    # Определяем, в каком канале используется команда
    if interaction.channel_id == DISCORD_CHANNEL_ID_BIG_FOLLOWERS:
        help_text = """
**Команды для отслеживания подписчиков:**
`/add_big <username>` — Добавить пользователя в список для отслеживания подписчиков
`/remove_big <username>` — Удалить пользователя из списка для отслеживания подписчиков
`/list_big` — Показать текущий список для отслеживания подписчиков
`/add_info` `/remove_info` `/list_info` — управление списком для info (отслеживание постов)
`/channels` — Показать доступные каналы
`/help` — Показать эту справку
"""
    else:
        help_text = """
**Команды для отслеживания подписок:**
`/add <username>` — Добавить пользователя в список целей для текущего канала
`/remove <username>` — Удалить пользователя из списка целей для текущего канала
`/list` — Показать текущий список целей для канала
`/all` — Показать все каналы и их списки целей
`/add_reply` `/remove_reply` `/targets_reply` — управление списком для reply (отправка в выделенный канал)
`/add_info` `/remove_info` `/list_info` — управление списком для info (отслеживание постов)
`/clear` — Очистить все сообщения в основном канале
`/channels` — Показать доступные каналы
`/help` — Показать эту справку
"""
    await interaction.response.send_message(help_text, ephemeral=True)

@tree.command(name="channels", description="Показать доступные каналы")
async def show_channels_slash(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="📋 Доступные каналы",
            description="Список всех доступных каналов в серверах:",
            color=0x00ff00
        )
        
        for guild in bot.guilds:
            guild_text = f"**Сервер: {guild.name}**\n"
            for channel in guild.text_channels:
                guild_text += f"  #{channel.name} (ID: {channel.id})\n"
            embed.add_field(name=guild.name, value=guild_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Ошибка при получении списка каналов: {e}", ephemeral=True)

@tree.command(name="all", description="Показать все каналы и их списки целей")
async def all_channels_slash(interaction: discord.Interaction):
    if is_panel_channel(interaction.channel_id):
        await interaction.response.send_message("Команды отключены в панели", ephemeral=True)
        return
    channels = get_all_channels()
    if not channels:
        await interaction.response.send_message("Нет настроенных каналов", ephemeral=True)
        return
    embed = discord.Embed(
        title="Все каналы и их списки целей",
        color=0xFF9800
    )
    for channel_id, targets in channels.items():
        channel_name = f"Канал {channel_id}"
        try:
            channel = bot.get_channel(int(channel_id))
            if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                channel_name = f"#{channel.name}"
        except Exception:
            pass
        targets_text = ", ".join(targets) if targets else "пусто"
        embed.add_field(
            name=channel_name,
            value=f"**{len(targets)} целей:** {targets_text}",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Команды info перемещены выше, перед on_ready для правильной синхронизации



# =============================================================================
# 🎛️ ПАНЕЛЬ УПРАВЛЕНИЯ С КНОПКАМИ
# =============================================================================

class ChannelCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Создать канал для таргетов", style=discord.ButtonStyle.primary, custom_id="create_targets_channel")
    async def create_targets_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            logger.info(f"🔘 Нажата кнопка создания канала пользователем {interaction.user.name} (ID: {interaction.user.id})")
            
            guild = interaction.guild
            if guild is None:
                logger.warning("❌ Попытка создать канал не на сервере")
                await interaction.response.send_message("❌ Доступно только на сервере", ephemeral=True)
                return

            base_name = "targets"
            name = f"{base_name}-{int(time.time())}"
            
            logger.info(f"🏗️ Создаём канал с именем: {name}")
            
            new_channel = await guild.create_text_channel(name=name)
            
            logger.success(f"Канал создан: #{new_channel.name} (ID: {new_channel.id})")
            
            # Сохраняем информацию о новом канале в diff_chats.json
            diff_chats = load_diff_chats()
            if str(new_channel.id) not in diff_chats:
                diff_chats[str(new_channel.id)] = {
                    "user_id": interaction.user.id,
                    "username": interaction.user.name,
                    "created_at": datetime.now().isoformat(),
                    "targets": []
                }
                save_diff_chats(diff_chats)
                logger.success(f"💾 Информация о канале сохранена в diff_chats.json")
            
            # Отправляем приветственное сообщение в новый канал
            welcome_embed = discord.Embed(
                title="🎯 Канал для отслеживания таргетов",
                description=(
                    f"Этот канал создан для отслеживания подписок пользователя **{interaction.user.name}**.\n\n"
                    "**Доступные команды:**\n"
                    "• `/add @username` - добавить таргет\n"
                    "• `/remove @username` - удалить таргет\n"
                    "• `/list` - показать список таргетов\n"
                    "• `/help` - справка по командам\n\n"
                    "**Важно:** Используйте команды только в этом канале!"
                ),
                color=0x00ff00
            )
            welcome_embed.set_footer(text=f"Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
            
            await new_channel.send(embed=welcome_embed)
            
            logger.success(f"📝 Приветственное сообщение отправлено в канал #{new_channel.name}")
            
            await interaction.response.send_message(f"✅ Создан канал #{new_channel.name} с приветственным сообщением!", ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания канала: {e}")
            try:
                await interaction.response.send_message(f"❌ Ошибка создания канала: {e}", ephemeral=True)
            except Exception:
                pass

class ReplyChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Reply Channel", style=discord.ButtonStyle.primary, custom_id="create_reply_channel")
    async def create_reply_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            logger.info(f"Нажата кнопка создания Reply канала пользователем {interaction.user.name} (ID: {interaction.user.id})")
            
            guild = interaction.guild
            if guild is None:
                logger.warning("Попытка создать канал не на сервере")
                await interaction.response.send_message("Доступно только на сервере", ephemeral=True)
                return

            # Создаем модальное окно для ввода имени канала
            modal = ChannelNameModal()
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Ошибка создания Reply канала: {e}")
            try:
                await interaction.response.send_message(f"Ошибка при создании канала: {e}", ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="Delete Reply Channel", style=discord.ButtonStyle.danger, custom_id="delete_reply_channel")
    async def delete_reply_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            logger.info(f"Нажата кнопка удаления Reply канала пользователем {interaction.user.name} (ID: {interaction.user.id})")
            logger.debug(f"Время: {datetime.now().isoformat()}")
            logger.debug(f"Канал: {interaction.channel.name} (ID: {interaction.channel.id})")
            logger.debug(f"Сервер: {interaction.guild.name if interaction.guild else 'None'}")
            
            guild = interaction.guild
            if guild is None:
                logger.warning("Попытка удалить канал не на сервере")
                await interaction.response.send_message("Доступно только на сервере", ephemeral=True)
                return
            
            # Ищем канал в категории x2-replies
            category = discord.utils.get(guild.categories, name="x2-replies")
            if not category:
                await interaction.response.send_message("Категория x2-replies не найдена", ephemeral=True)
                return
            
            # Показываем список каналов для удаления
            channels = category.channels
            if not channels:
                await interaction.response.send_message("В категории x2-replies нет каналов для удаления", ephemeral=True)
                return
            
            # Создаем список каналов для выбора
            options = []
            for channel in channels:
                if isinstance(channel, discord.TextChannel):
                    options.append(discord.SelectOption(label=f"#{channel.name}", value=str(channel.id), description=f"Канал {channel.name}"))
            
            if not options:
                await interaction.response.send_message("Нет текстовых каналов для удаления", ephemeral=True)
                return
            
            # Создаем select menu для выбора канала с подтверждением
            select = discord.ui.Select(
                placeholder="Выберите канал для удаления",
                options=options[:25],  # Discord ограничивает 25 опций
                custom_id="delete_reply_channel_select"
            )
            
            async def select_callback(select_interaction: discord.Interaction):
                try:
                    logger.info(f"Выбран канал для удаления пользователем {select_interaction.user.name}")
                    logger.debug(f"Данные выбора: {select_interaction.data}")
                    
                    channel_id = int(select_interaction.data["values"][0])
                    channel = guild.get_channel(channel_id)
                    if channel:
                        # Создаем кнопки подтверждения
                        confirm_view = ConfirmDeleteView(channel)
                        await select_interaction.response.send_message(
                            f"⚠️ **Подтверждение удаления**\n\n"
                            f"Вы действительно хотите удалить канал #{channel.name}?\n"
                            f"**Это действие нельзя отменить!**",
                            view=confirm_view,
                            ephemeral=True
                        )
                        
                        logger.success(f"Создан ConfirmDeleteView для канала {channel.name} (ID: {channel.id})")
                    else:
                        await select_interaction.response.send_message("Канал не найден", ephemeral=True)
                        logger.warning(f"Канал с ID {channel_id} не найден")
                except Exception as e:
                    logger.error(f"Ошибка в select_callback: {e}")
                    await select_interaction.response.send_message(f"Ошибка при выборе канала: {e}", ephemeral=True)
            
            select.callback = select_callback
            view = discord.ui.View()
            view.add_item(select)
            
            await interaction.response.send_message("Выберите канал для удаления:", view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления Reply канала: {e}")
            logger.debug(f"🔍 Тип ошибки: {type(e).__name__}")
            logger.debug(f"🔍 Детали: {str(e)}")
            try:
                await interaction.response.send_message(f"❌ Ошибка при удалении канала: {e}", ephemeral=True)
            except Exception as e2:
                logger.error(f"❌ Дополнительная ошибка при отправке сообщения: {e2}")

class ChannelNameModal(discord.ui.Modal, title="Создание Reply канала"):
    def __init__(self):
        super().__init__()
        self.channel_name = discord.ui.TextInput(
            label="Имя канала",
            placeholder="Введите имя для нового канала (без пробелов)",
            min_length=1,
            max_length=32,
            required=True,
            custom_id="channel_name_input"
        )
        self.add_item(self.channel_name)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_name = self.channel_name.value.strip()
            
            # Проверяем валидность имени канала
            if not channel_name or len(channel_name) < 1:
                await interaction.response.send_message("❌ Имя канала не может быть пустым", ephemeral=True)
                return
            
            # Заменяем пробелы на дефисы и убираем специальные символы
            channel_name = channel_name.replace(" ", "-").replace("_", "-")
            channel_name = "".join(c for c in channel_name if c.isalnum() or c == "-")
            
            if not channel_name:
                await interaction.response.send_message("❌ Некорректное имя канала", ephemeral=True)
                return
            
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message("❌ Ошибка: не удалось получить информацию о сервере", ephemeral=True)
                return

            # Создаем категорию x2-replies если её нет
            category = discord.utils.get(guild.categories, name="x2-replies")
            if not category:
                category = await guild.create_category("x2-replies")
                logger.success(f"✅ Создана категория {category.name}")
                await interaction.response.send_message(f"✅ Создана категория {category.name}", ephemeral=True)
            
            # Проверяем, не существует ли уже канал с таким именем
            existing_channel = discord.utils.get(category.channels, name=channel_name)
            if existing_channel:
                await interaction.response.send_message(f"❌ Канал с именем #{channel_name} уже существует", ephemeral=True)
                return
            
            # Создаем канал в категории
            channel = await guild.create_text_channel(channel_name, category=category)
            
            logger.success(f"✅ Reply канал создан: #{channel.name} (ID: {channel.id})")
            
            await interaction.response.send_message(
                f"✅ **Канал создан успешно!**\n\n"
                f"**Имя:** #{channel.name}\n"
                f"**Категория:** {category.name}\n"
                f"**ID:** {channel.id}",
                ephemeral=True
            )
            
            # --- ДОБАВИТЬ ---
            reply_targets_path = os.path.join(DATA_DIR_REPLY, f"reply_{channel.id}.txt")
            try:
                with open(reply_targets_path, 'w', encoding='utf-8') as f:
                    f.write("# Список пользователей для отслеживания ответов\n")
                    f.write("# Каждый пользователь на новой строке\n")
                    logger.success(f"Создан файл {reply_targets_path}")
            except Exception as e:
                logger.error(f"Ошибка при создании файла {reply_targets_path}: {e}")

            # Обновляем справочник каналов
            channels_meta_path = os.path.join(DATA_DIR_REPLY, "reply_channels.json")
            try:
                if os.path.exists(channels_meta_path):
                    try:
                        with open(channels_meta_path, 'r', encoding='utf-8') as f:
                            channels_meta = json.load(f)
                    except Exception as e:
                        logger.error(f"Ошибка при чтении {channels_meta_path}: {e}")
                        channels_meta = {}
                else:
                    channels_meta = {}
                
                channels_meta[str(channel.id)] = {
                    "id": str(channel.id),
                    "name": channel.name,
                    "created_at": datetime.now().isoformat()
                }
                
                try:
                    with open(channels_meta_path, 'w', encoding='utf-8') as f:
                        json.dump(channels_meta, f, ensure_ascii=False, indent=2)
                    logger.success(f"Обновлен справочник каналов для {channel.name} (ID: {channel.id})")
                except Exception as e:
                    logger.error(f"Ошибка при записи {channels_meta_path}: {e}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении reply_channels.json: {e}")
            # --- КОНЕЦ ДОБАВЛЕНИЯ ---
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания канала через модальное окно: {e}")
            try:
                await interaction.response.send_message(f"❌ Ошибка при создании канала: {e}", ephemeral=True)
            except Exception:
                pass

class ConfirmDeleteView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=None)  # Убираем timeout для persistent view
        self.channel = channel

    @discord.ui.button(label="Подтвердить удаление", style=discord.ButtonStyle.danger, custom_id="confirm_delete_reply")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.Button):
        try:
            logger.info(f"🔘 Нажата кнопка подтверждения удаления канала {self.channel.name}")
            logger.debug(f"🔍 Пользователь: {interaction.user.name} (ID: {interaction.user.id})")
            logger.debug(f"🔍 Время: {datetime.now().isoformat()}")
            
            channel_name = self.channel.name
            channel_id = self.channel.id
            await self.channel.delete()
            # Удаляем все связанные файлы
            reply_file = os.path.join(DATA_DIR_REPLY, f"reply_{channel_id}.txt")
            usernames = []
            if os.path.exists(reply_file):
                try:
                    with open(reply_file, 'r', encoding='utf-8') as f:
                        usernames = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                    os.remove(reply_file)
                    logger.debug(f"Удален файл {reply_file} с {len(usernames)} пользователями")
                except Exception as e:
                    logger.error(f"Ошибка при чтении/удалении файла {reply_file}: {e}")
            for username in usernames:
                reply_json = os.path.join(DATA_DIR_REPLY, f"{username}_replies.json")
                if os.path.exists(reply_json):
                    os.remove(reply_json)
            channel_dir = os.path.join(NEW_DIR_REPLY, str(channel_id))
            if os.path.exists(channel_dir):
                shutil.rmtree(channel_dir)
            # Удаляем запись из reply_channels.json
            channels_meta_path = os.path.join(DATA_DIR_REPLY, "reply_channels.json")
            try:
                if os.path.exists(channels_meta_path):
                    try:
                        with open(channels_meta_path, 'r', encoding='utf-8') as f:
                            channels_meta = json.load(f)
                        
                        if str(channel_id) in channels_meta:
                            del channels_meta[str(channel_id)]
                            try:
                                with open(channels_meta_path, 'w', encoding='utf-8') as f:
                                    json.dump(channels_meta, f, ensure_ascii=False, indent=2)
                                logger.success(f"Удалена запись канала {channel_id} из reply_channels.json")
                            except Exception as e:
                                logger.error(f"Ошибка при записи {channels_meta_path}: {e}")
                    except Exception as e:
                        logger.error(f"Ошибка при чтении {channels_meta_path}: {e}")
            except Exception as e:
                logger.error(f"Ошибка при удалении записи из reply_channels.json: {e}")
                logger.success(f"Канал #{channel_name} удален пользователем {interaction.user.name}")
            await interaction.response.send_message(
                f"**Канал удален!**\n\nКанал #{channel_name} был успешно удален.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Ошибка удаления канала {self.channel.name}: {e}")
            try:
                await interaction.response.send_message(f"Ошибка при удалении канала: {e}", ephemeral=True)
            except Exception:
                pass

# Аналогичный Confirm для info-каналов (удаляем файлы last_info)
class ConfirmDeleteInfoView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=60)
        self.channel = channel

    @discord.ui.button(label="Подтвердить удаление", style=discord.ButtonStyle.danger, custom_id="confirm_delete_info")
    async def confirm_delete_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel_name = self.channel.name
            channel_id = self.channel.id
            await self.channel.delete()
            # Удаляем связанный txt
            txt_path = os.path.join(DATA_DIR_INFO, f"info_{channel_id}.txt")
            if os.path.exists(txt_path):
                try:
                    os.remove(txt_path)
                    logger.debug(f"Удален файл {txt_path}")
                except Exception as e:
                    logger.error(f"Ошибка при удалении файла {txt_path}: {e}")
            
            # --- ДОБАВИТЬ (по аналогии с reply_channels) ---
            # Удаляем запись из info_channels.json с метаданными
            channels_meta_path = os.path.join(DATA_DIR_INFO, "info_channels.json")
            try:
                if os.path.exists(channels_meta_path):
                    try:
                        with open(channels_meta_path, 'r', encoding='utf-8') as f:
                            channels_meta = json.load(f)
                        if str(channel_id) in channels_meta:
                            del channels_meta[str(channel_id)]
                            try:
                                with open(channels_meta_path, 'w', encoding='utf-8') as f:
                                    json.dump(channels_meta, f, ensure_ascii=False, indent=2)
                                logger.success(f"✅ Удалена запись из info_channels.json для канала {channel_id}")
                            except Exception as e:
                                logger.error(f"❌ Ошибка при записи {channels_meta_path}: {e}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при чтении {channels_meta_path}: {e}")
            except Exception as e:
                logger.error(f"❌ Ошибка при удалении записи из info_channels.json: {e}")
            # --- КОНЕЦ ДОБАВЛЕНИЯ ---
            
            # Обновляем info_channels.json (список таргетов)
            ensure_info_storage_exists()
            try:
                try:
                    with open(INFO_CHANNELS_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if str(channel_id) in data:
                        del data[str(channel_id)]
                        try:
                            with open(INFO_CHANNELS_FILE, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            logger.success(f"Удалена запись канала {channel_id} из info_channels.json")
                        except Exception as e:
                            logger.error(f"Ошибка при записи {INFO_CHANNELS_FILE}: {e}")
                except Exception as e:
                    logger.error(f"Ошибка при чтении {INFO_CHANNELS_FILE}: {e}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении info_channels.json: {e}")
            
            # Удаляем файлы истории постов для всех таргетов этого канала
            try:
                targets = load_info_targets_for_channel(channel_id)
                for username in targets:
                    history_file = os.path.join(DATA_DIR_INFO, f"{username}_info.json")
                    if os.path.exists(history_file):
                        try:
                            os.remove(history_file)
                            logger.debug(f"Удален файл истории {history_file}")
                        except Exception as e:
                            logger.error(f"Ошибка при удалении файла истории {history_file}: {e}")
                logger.success(f"Удалены файлы истории для {len(targets)} таргетов канала {channel_id}")
            except Exception as e:
                logger.error(f"Ошибка при удалении файлов истории: {e}")
            logger.success(f"✅ Info-канал #{channel_name} удален пользователем {interaction.user.name}")
            
            await interaction.response.send_message(
                f"✅ **Info-канал удален!**\n\nКанал #{channel_name} был успешно удален.", ephemeral=True
            )
        except Exception as e:
            try:
                await interaction.response.send_message(f"Ошибка при удалении info-канала: {e}", ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="❌ Отменить", style=discord.ButtonStyle.secondary, custom_id="cancel_delete")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            logger.info(f"Удаление канала #{self.channel.name} отменено пользователем {interaction.user.name}")
            
            await interaction.response.send_message(
                f"**Удаление отменено**\n\n"
                f"Канал #{self.channel.name} не был удален.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка при отмене удаления: {e}")
            try:
                await interaction.response.send_message(f"❌ Ошибка при отмене: {e}", ephemeral=True)
            except Exception:
                pass

# =============================================================================
# 🔧 ФУНКЦИИ ОБЕСПЕЧЕНИЯ РАБОТЫ ПАНЕЛЕЙ
# =============================================================================

async def ensure_control_panel_posted():
    try:
        logger.debug("Попытка разместить панель управления")
        
        os.makedirs(os.path.dirname(REPLY_PANEL_MESSAGE_ID_FILE), exist_ok=True)
        channel = bot.get_channel(CONTROL_PANEL_CHANNEL_ID)
        
        if channel is None:
            logger.warning(f"Канал {CONTROL_PANEL_CHANNEL_ID} не найден")
            return
        
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            logger.warning(f"Канал {CONTROL_PANEL_CHANNEL_ID} не является текстовым каналом")
            return

        logger.info(f"Канал найден: {channel.name} (ID: {channel.id})")

        message_id = None
        if os.path.exists(REPLY_PANEL_MESSAGE_ID_FILE):
            try:
                with open(REPLY_PANEL_MESSAGE_ID_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        message_id = int(content)
                        logger.info(f"Найден сохранённый ID сообщения: {message_id}")
            except Exception as e:
                logger.warning(f"Ошибка чтения ID сообщения: {e}")
                message_id = None

        if message_id:
            try:
                existing_message = await channel.fetch_message(message_id)
                logger.info(f"Сообщение {message_id} уже существует, панель не создаётся")
                return
            except Exception as e:
                logger.warning(f"Сообщение {message_id} не найдено, создаём новое: {e}")

        embed = discord.Embed(
            title="Reply Channels",
            description=(
                "Create/Delete - создать или удалить канал в категории x2-replies\n"
                "Можно отслеживать таргеты в соотвествии с вашей категории\n"
            ),
            color=0x2ecc71,
        )
        
        logger.info(f"Отправляем панель Reply Channels в канал {channel.name}")
        
        sent = await channel.send(embed=embed, view=ReplyChannelView())
        
        logger.success(f"Панель управления отправлена, ID сообщения: {sent.id}")
        
        try:
            with open(REPLY_PANEL_MESSAGE_ID_FILE, 'w', encoding='utf-8') as f:
                f.write(str(sent.id))
            logger.success(f"ID сообщения {sent.id} сохранён в файл {REPLY_PANEL_MESSAGE_ID_FILE}")
        except Exception as e:
            logger.error(f"Ошибка сохранения ID сообщения в {REPLY_PANEL_MESSAGE_ID_FILE}: {e}")
                
    except Exception as e:
        logger.error(f"Критическая ошибка в ensure_control_panel_posted: {e}")

# =============================================================================
# 📤 ОТПРАВКА В DISCORD
# =============================================================================
async def send_discord(username, bio, name, avatar_url, found_by, channel_id, followers="", created_at="", banner=""):
    global bot_ready
    if not bot_ready:
        return
    try:
        channel = bot.get_channel(channel_id)
        if channel is None:
            logger.warning(f"Канал {channel_id} не найден")
            return
        # Поддержка TextChannel, DMChannel, Thread
        if not isinstance(channel, (discord.TextChannel, discord.DMChannel, discord.Thread)):
            logger.warning(f"Канал {channel_id} не поддерживает отправку сообщений")
            return
        
        # Для канала 1391418960494465084 отправляем простой текст вместо embed
        if channel_id == DISCORD_CHANNEL_ID:
            message = f"**@{username}** - {name}\n{bio[:100]}{'...' if len(bio) > 100 else ''}\nНайден через @{found_by}"
            await channel.send(message)
        else:
            # Для других каналов создаем embed
            embed = discord.Embed(
                title=f"{username}",
                url=f"https://twitter.com/{username}",
                description=bio[:200] + "..." if len(bio) > 200 else bio,
                color=0xFF9800
            )
            embed.add_field(name="Name", value=f"{name}", inline=True)
            embed.add_field(name="Followed by", value=f"{found_by}", inline=True)
            embed.add_field(name="Followers", value=f"{followers}", inline=True)
            discord_timestamp = convert_twitter_time_to_discord_timestamp(created_at)
            embed.add_field(name="Created at", value=discord_timestamp, inline=True)
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)
            embed.set_footer(text="Twitter Monitor Bot")
            if banner:
                embed.set_image(url=banner)
            await channel.send(embed=embed)
        
        logger.success(f"Отправлено сообщение для @{username} (найден @{found_by})")
    except Exception as e:
        logger.error(f"Ошибка отправки @{username}: {e}")

# =============================================================================
# 🛠️ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ DISCORD
# =============================================================================
def run_discord_bot():
    try:
        logger.info("🔗 Подключаюсь к Discord...")
        os.environ['PYTHONPATH'] = ''
        bot.run(BOT_TOKEN, log_handler=None)
    except Exception as e:
        logger.error(f"Ошибка подключения к Discord: {e}")
        logger.info("💡 Проверьте токен бота в Discord Developer Portal")

def wait_for_discord_ready(timeout=30):
    waited = 0
    while not bot_ready and waited < timeout:
        time.sleep(0.2)  # Эта функция вызывается из синхронного кода
        waited += 0.2
    if not bot_ready:
        logger.warning(f"Discord бот не готов после {timeout} секунд ожидания!")
        return False
    return True

def is_discord_bot_ready():
    """Проверяет готовность Discord бота"""
    return bot_ready and bot.is_ready()

# =============================================================================
# 📁 РАБОТА С ФАЙЛАМИ И СПИСКАМИ
# =============================================================================
def load_targets():
    """Загружает список целей из targets.txt (legacy)"""
    if not os.path.exists(TARGETS_FILE):
        logger.debug(f"Файл {TARGETS_FILE} не найден, возвращаем пустой список")
        return []
    try:
        with open(TARGETS_FILE, "r", encoding="utf-8") as f:
            targets = [line.strip() for line in f if line.strip()]
        logger.debug(f"Загружено {len(targets)} целей из {TARGETS_FILE}")
        return targets
    except Exception as e:
        logger.error(f"Ошибка при загрузке {TARGETS_FILE}: {e}")
        return []

def load_diff_chats():
    """Загружает diff_chats.json"""
    if not os.path.exists(DIFF_CHATS_FILE):
        logger.debug(f"Файл {DIFF_CHATS_FILE} не найден, возвращаем пустой словарь")
        return {}
    try:
        with open(DIFF_CHATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"Загружено {len(data)} каналов из {DIFF_CHATS_FILE}")
        return data
    except Exception as e:
        logger.error(f"Ошибка загрузки {DIFF_CHATS_FILE}: {e}")
        return {}

def save_diff_chats(data):
    """Сохраняет diff_chats.json"""
    try:
        with open(DIFF_CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.debug(f"Сохранено {len(data)} каналов в {DIFF_CHATS_FILE}")
    except Exception as e:
        logger.error(f"Ошибка сохранения {DIFF_CHATS_FILE}: {e}")

def load_targets_for_channel(channel_id):
    """Загружает список целей для канала"""
    channel_id_str = str(channel_id)
    diff_chats = load_diff_chats()
    return diff_chats.get(channel_id_str, [])

def save_targets_for_channel(channel_id, targets):
    """Сохраняет список целей для канала"""
    channel_id_str = str(channel_id)
    diff_chats = load_diff_chats()
    diff_chats[channel_id_str] = targets
    save_diff_chats(diff_chats)

def get_all_channels():
    """Возвращает все каналы и их цели"""
    return load_diff_chats()

def load_json(path):
    if not os.path.exists(path):
        logger.debug(f"Файл {path} не найден, возвращаем пустой список")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"Загружено {len(data)} записей из {path}")
        return data
    except Exception as e:
        logger.error(f"Ошибка при загрузке {path}: {e}")
        return []

def save_json(data, path):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Сохранено {len(data)} записей в {path}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении {path}: {e}")

def save_targets(targets):
    """Сохраняет список целей в targets.txt (legacy)"""
    try:
        with open(TARGETS_FILE, "w", encoding="utf-8") as f:
            for target in targets:
                f.write(f"{target}\n")
        logger.debug(f"Сохранено {len(targets)} целей в {TARGETS_FILE}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении {TARGETS_FILE}: {e}")

def find_new_followings(old, new):
    """Находит новые подписки по username"""
    old_usernamees = {u[2] for u in old}
    return [u for u in new if u[2] not in old_usernamees]

# --- Twitter API для больших подписчиков ---
def get_id_big(username_big, cookies_id, headers_id, params_id):
    headers = headers_id.copy()
    params = params_id.copy()
    headers['referer'] = f'https://x.com/{username_big}/following'
    params['variables'] = json.dumps({"screen_name": username_big})
    url = "https://x.com/i/api/graphql/x3RLKWW1Tl7JgU7YtGxuzw/UserByScreenName"
    response = requests.get(url, params=params, cookies=cookies_id, headers=headers)
    if response.status_code == 200:
        try:
            return response.json()['data']['user']['result']['rest_id']
        except Exception as e:
            logger.error(f'Ошибка при парсинге user_id: {e}, {response.text}')
            return None
    else:
        logger.error(f'Ошибка при запросе user_id: {response.status_code}, {response.text}')
        return None

def get_big_followers(user_id_big, username_big, cookies_big, headers_big, params_big):
    """Получает список подписчиков пользователя"""
    headers = headers_big.copy()
    params = params_big.copy()
    headers['referer'] = f'https://x.com/{username_big}/verified_followers'
    params['variables'] = json.dumps({"userId": user_id_big, "count": 20, "includePromotedContent": False})
    url = "https://x.com/i/api/graphql/U_YXAm7JJsfvjFUJwObTdw/BlueVerifiedFollowers"
    response = requests.get(url, params=params, cookies=cookies_big, headers=headers)
    if response.status_code == 200:
        try:
            instructions = response.json()['data']['user']['result']['timeline']['timeline']['instructions']
        except Exception as e:
            logger.error(f'Ошибка при парсинге подписчиков: {e}, {response.text}')
            return []
        users = []
        for instr in instructions:
            if isinstance(instr, dict) and instr.get('type') == 'TimelineAddEntries':
                for entry in instr.get('entries', []):
                    content = entry.get('content', {})
                    if content.get('entryType') == 'TimelineTimelineItem':
                        try:
                            user = content['itemContent']['user_results']['result']
                            core = user.get('core', {}) or {}
                            legacy = user.get('legacy', {}) or {}
                            avatar_url = user.get('avatar', {}).get('image_url', '')
                            created_at = core.get('created_at', '')
                            username = core.get('screen_name', "")
                            name = core.get('name', '')
                            bio = legacy.get('description', "")
                            followers_count = legacy.get('followers_count', 0)
                            banner = legacy.get('profile_banner_url', "")
                            # Фильтруем только подписчиков с 1500+ followers (как в get_followers_emoji)
                            if followers_count >= 1500:
                                users.append([avatar_url, created_at, username, name, bio, followers_count, banner])
                        except Exception:
                            continue
        return users
    else:
        logger.error(f'Ошибка при запросе подписчиков: {response.status_code}, {response.text}')
        return []

def get_followers_emoji(followers_count):
    """Возвращает количество смайликов в зависимости от количества подписчиков"""
    if followers_count >= 10000:
        return "🟠🟠🟠"
    elif followers_count >= 5000:
        return "🟠🟠"
    elif followers_count >= 1500:
        return "🟠"
    else:
        return ""

def validate_username(username):
    """Проверяет корректность username для Twitter"""
    if not username:
        return False, "Username не может быть пустым"
    
    # Убираем @ в начале, если есть
    username = username.lstrip('@').strip()
    
    if not username:
        return False, "Username не может быть пустым после удаления @"
      
    if len(username) < 1:
        return False, "Username слишком короткий"

    # Проверяем, что не содержит только цифры
    if username.isdigit():
        return False, "Username не может состоять только из цифр"
    
    return True, username

# =============================================================================
# 👥 ФУНКЦИИ ДЛЯ РАБОТЫ С БОЛЬШИМИ ПОДПИСЧИКАМИ
# =============================================================================
def load_big_targets():
    """Загружает список целей для отслеживания подписчиков"""
    big_targets_file = os.path.join(DATA_DIR_BIG, "bigfollow.txt")
    if not os.path.exists(big_targets_file):
        logger.debug(f"Файл {big_targets_file} не найден, возвращаем пустой список")
        return []
    try:
        with open(big_targets_file, "r", encoding="utf-8") as f:
            targets = [line.strip() for line in f if line.strip()]
        logger.debug(f"Загружено {len(targets)} целей для больших подписчиков из {big_targets_file}")
        return targets
    except Exception as e:
        logger.error(f"Ошибка загрузки {big_targets_file}: {e}")
        return []

def save_big_targets(targets):
    """Сохраняет список целей для отслеживания подписчиков"""
    big_targets_file = os.path.join(DATA_DIR_BIG, "bigfollow.txt")
    try:
        with open(big_targets_file, "w", encoding="utf-8") as f:
            for target in targets:
                f.write(f"{target}\n")
        logger.debug(f"Сохранено {len(targets)} целей для больших подписчиков в {big_targets_file}")
    except Exception as e:
        logger.error(f"Ошибка сохранения {big_targets_file}: {e}")

def find_new_big_followers(old, new):
    """Находит новых подписчиков по username"""
    old_usernames = {u[2] for u in old}
    return [u for u in new if u[2] not in old_usernames]

# =============================================================================
# 🔍 СКАНИРОВАНИЕ БОЛЬШИХ ПОДПИСЧИКОВ
# =============================================================================
def scan_big_followers():
    """Сканирует подписчиков для больших аккаунтов"""
    os.makedirs(DATA_DIR_BIG, exist_ok=True)
    os.makedirs(OLD_DIR_BIG, exist_ok=True)
    os.makedirs(NEW_DIR_BIG, exist_ok=True)
    
    big_targets = load_big_targets()
    if not big_targets:
        logger.warning("❌ Нет настроенных целей для отслеживания подписчиков")
        return
    
    logger.info(f"📡 Сканируем подписчиков для {len(big_targets)} целей")
    
    for username_big in big_targets:
        logger.info(f'🔍 Сканируем подписчиков пользователя: {username_big}')
        user_id_big = get_id_big(username_big, TWITTER_COOKIES, headers_id, params_id)
        if not user_id_big:
            logger.error(f'❌ Ошибка при получении user_id для {username_big}')
            continue
        
        followers = get_big_followers(user_id_big, username_big, cookies_big, headers_big, params_big)
        if not followers:
            logger.error(f'❌ Ошибка при получении подписчиков для {username_big}')
            continue
        
        # Используем папку old_followers для хранения старых данных
        data_path = os.path.join(OLD_DIR_BIG, f'{username_big}_followers.json')
        old_followers = load_json(data_path)
        
        if not old_followers:
            save_json(followers, data_path)
            logger.success(f'✅ Первый запуск для {username_big}, сохранено {len(followers)} подписчиков (1500+ followers)')
            continue
        
        new_users = find_new_big_followers(old_followers, followers)
        if new_users:
            new_path = os.path.join(NEW_DIR_BIG, f'new_{username_big}_followers.json')
            save_json(new_users, new_path)
            logger.success(f'🎯 Найдено {len(new_users)} новых подписчиков для {username_big}')
        else:
            logger.info(f'⏭️ Новых подписчиков для {username_big} не найдено')
        
        # Обновляем старые данные
        save_json(followers, data_path)
    
    logger.info("📤 Отправляем новых подписчиков в Discord...")
    send_new_big_followers_to_discord()
    logger.success("✅ Отправка больших подписчиков в Discord завершена")

# =============================================================================
# 📤 ОТПРАВКА БОЛЬШИХ ПОДПИСЧИКОВ В DISCORD
# =============================================================================
async def send_big_follower_discord(username_big, bigfollow, description, followers_count, channel_id, avatar_url="", banner=""):
    """Отправляет embed с информацией о новом подписчике"""
    global bot_ready
    if not bot_ready:
        return
    
    try:
        channel = bot.get_channel(channel_id)
        if channel is None:
            logger.warning(f"Канал {channel_id} не найден")
            return
        
        if not isinstance(channel, (discord.TextChannel, discord.DMChannel, discord.Thread)):
            logger.warning(f"Канал {channel_id} не поддерживает отправку сообщений")
            return
        
        emoji = get_followers_emoji(followers_count)
        # Отправляем только если есть эмодзи (1500+ followers)
        if not emoji:
            logger.info(f"Пропускаем @{bigfollow} (менее 1500 followers)")
            return
        
        title = f"{emoji} {bigfollow} subscribed to {username_big}"
        
        embed = discord.Embed(
            title=title,
            url=f"https://twitter.com/{bigfollow}",
            description=description[:200] + "..." if len(description) > 200 else description,
            color=0xFF8C00 
        )
        embed.add_field(name="Followers", value=f"{followers_count:,}", inline=True)
        embed.add_field(name="Target User", value=f"@{username_big}", inline=True)
        embed.set_footer(text="Big Followers Monitor")
        
        # Добавляем аватарку
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        
        # Добавляем баннер
        if banner:
            embed.set_image(url=banner)
        
        await channel.send(embed=embed)
        logger.success(f"Отправлен embed для подписчика @{bigfollow} (отслеживаем @{username_big})")
    except Exception as e:
        logger.error(f"Ошибка отправки подписчика @{bigfollow}: {e}")

def send_new_big_followers_to_discord():
    """Отправляет всех новых подписчиков из файлов new_big в Discord"""
    global bot_ready
    if not wait_for_discord_ready(timeout=30):
        return
    
    files_processed = 0
    logger.info(f"🔍 Проверяем папку {NEW_DIR_BIG} на новые файлы...")
    
    if not os.path.exists(NEW_DIR_BIG):
        return
    
    for filename in os.listdir(NEW_DIR_BIG):
        if not filename.endswith('.json') or filename.startswith('.'):
            continue
        
        filepath = os.path.join(NEW_DIR_BIG, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                users = json.load(f)
            
            if not users:
                logger.warning(f"⚠️ Файл {filename} пустой, пропускаем")
                continue
            
            username_big = filename.replace('new_', '').replace('_followers.json', '')
            
            logger.info(f"📤 Отправляем {len(users)} новых подписчиков от @{username_big}...")
            
            for i, user_data in enumerate(users, 1):
                avatar_url = user_data[0]
                created_at = user_data[1]
                bigfollow = user_data[2]  # username подписчика
                name = user_data[3]
                description = user_data[4]
                followers_count = user_data[5]
                banner = user_data[6]
                
                logger.debug(f"📨 Отправляем {i}/{len(users)}: @{bigfollow} (отслеживаем @{username_big})")
                # Отправляем в Discord через asyncio.run_coroutine_threadsafe
                try:
                    asyncio.run_coroutine_threadsafe(
                        send_big_follower_discord(username_big, bigfollow, description, followers_count, DISCORD_CHANNEL_ID_BIG_FOLLOWERS, avatar_url, banner),
                        bot.loop
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке @{bigfollow}: {e}")
                time.sleep(0.5)
            
            logger.success(f"✅ Отправлено: {filename}")
            
            files_processed += 1
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке {filename}: {e}")
    
    logger.info(f"🎯 Обработано файлов больших подписчиков: {files_processed}")

# =============================================================================
# 🎮 DISCORD КОМАНДЫ ДЛЯ БОЛЬШИХ ПОДПИСЧИКОВ
# =============================================================================
@tree.command(name="add_big", description="Добавить пользователя в список для отслеживания подписчиков")
@app_commands.describe(username="Ник пользователя (без @)")
async def add_big_target_slash(interaction: discord.Interaction, username: str):
    if is_panel_channel(interaction.channel_id):
        await interaction.response.send_message("Команды отключены в панели", ephemeral=True)
        return
    # Проверяем, что команда используется в правильном канале
    if interaction.channel_id != DISCORD_CHANNEL_ID_BIG_FOLLOWERS:
        await interaction.response.send_message("❌ Эта команда доступна только в канале для отслеживания больших подписчиков", ephemeral=True)
        return
    
    # Валидация username
    is_valid, result = validate_username(username)
    if not is_valid:
        await interaction.response.send_message(f"❌ {result}", ephemeral=True)
        return
    
    username = result  # result содержит очищенный username
    
    targets = load_big_targets()
    if username in targets:
        await interaction.response.send_message(f"❌ {username} уже есть в списке для отслеживания подписчиков", ephemeral=True)
        return
    
    targets.append(username)
    save_big_targets(targets)
    await interaction.response.send_message(f"✅ {username} добавлен в список для отслеживания подписчиков. Всего: {len(targets)}", ephemeral=True)

@tree.command(name="remove_big", description="Удалить пользователя из списка для отслеживания подписчиков")
@app_commands.describe(username="Ник пользователя (без @)")
async def remove_big_target_slash(interaction: discord.Interaction, username: str):
    if is_panel_channel(interaction.channel_id):
        await interaction.response.send_message("Команды отключены в панели", ephemeral=True)
        return
    # Проверяем, что команда используется в правильном канале
    if interaction.channel_id != DISCORD_CHANNEL_ID_BIG_FOLLOWERS:
        await interaction.response.send_message("❌ Эта команда доступна только в канале для отслеживания больших подписчиков", ephemeral=True)
        return
    
    # Валидация username
    is_valid, result = validate_username(username)
    if not is_valid:
        await interaction.response.send_message(f"❌ {result}", ephemeral=True)
        return
    username = result  # result содержит очищенный username
    targets = load_big_targets()
    if username not in targets:
        await interaction.response.send_message(f"{username} не найден в списке для отслеживания подписчиков", ephemeral=True)
        return
    targets.remove(username)
    save_big_targets(targets)
    await interaction.response.send_message(f"✅ {username} удалён из списка для отслеживания подписчиков. Осталось: {len(targets)}", ephemeral=True)

@tree.command(name="list_big", description="Показать текущий список для отслеживания подписчиков")
async def list_big_target_slash(interaction: discord.Interaction):
    if is_panel_channel(interaction.channel_id):
        await interaction.response.send_message("Команды отключены в панели", ephemeral=True)
        return
    # Проверяем, что команда используется в правильном канале
    if interaction.channel_id != DISCORD_CHANNEL_ID_BIG_FOLLOWERS:
        await interaction.response.send_message("❌ Эта команда доступна только в канале для отслеживания больших подписчиков", ephemeral=True)
        return
    
    targets = load_big_targets()
    if not targets:
        await interaction.response.send_message("Список для отслеживания подписчиков пуст", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"Список для отслеживания подписчиков – {len(targets)}",
        description="\n".join(f"@{t}" for t in targets),
        color=0xFF8C00
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# =============================================================================
# 📰 INFO МОДУЛЬ - ПОЛУЧЕНИЕ ПОСТОВ/РЕПОСТОВ
# =============================================================================
def get_latest_info(user_id, username, cookies_info, headers_info, params_info):
    """Получает последние посты/репосты пользователя через Twitter API"""
    try:
        headers = headers_info.copy()
        params = params_info.copy()
        
        # Форматируем параметры с динамическими значениями
        headers['referer'] = f'https://x.com/{username}'
        params['variables'] = json.dumps({"userId": user_id, "count": 20, "includePromotedContent": True, "withCommunity": True, "withVoice": True})
        
        url = "https://x.com/i/api/graphql/BqvqNsqColIQbpX1_NmEwg/UserTweets"
        
        response = requests.get(url, params=params, cookies=cookies_info, headers=headers)
        if response.status_code == 200:
            try:
                json_data = response.json()
                return json_data
            except Exception as e:
                logger.error(f"Ошибка при парсинге JSON для {username}: {e}")
                return None
        else:
            logger.error(f"Ошибка HTTP {response.status_code} для {username}: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Общая ошибка при запросе info для {username}: {e}")
        return None

# =============================================================================
# 🔍 ИЗВЛЕЧЕНИЕ ПОСТОВ ИЗ ОТВЕТА INFO
# =============================================================================
def extract_posts_from_info(json_data):
    """Извлекает список постов из ответа info (UserTweets)"""
    posts = []
    try:
        # Проверяем структуру ответа
        if not json_data or 'data' not in json_data:
            logger.debug("Неверная структура JSON ответа")
            return posts
        
        user_data = json_data['data'].get('user', {})
        if not user_data:
            logger.debug("Данные пользователя не найдены в ответе")
            return posts
        
        result = user_data.get('result', {})
        if not result:
            logger.debug("Результат пользователя не найден")
            return posts
        
        # В ex.json структура: data.user.result.timeline.timeline.instructions
        timeline = result.get('timeline', {})
        if not timeline:
            logger.debug("Timeline не найден")
            return posts
        
        timeline_inner = timeline.get('timeline', {})
        if not timeline_inner:
            logger.debug("Внутренний timeline не найден")
            return posts
        
        instructions = timeline_inner.get('instructions', [])
        if not instructions:
            logger.debug("Инструкции timeline не найдены")
            return posts
        
        logger.debug(f"Найдено {len(instructions)} инструкций timeline")
        
        for instr in instructions:
            if instr.get('type') == 'TimelineAddEntries':
                entries = instr.get('entries', [])
                
                for entry in entries:
                    try:
                        content = entry.get('content', {})
                        if content.get('entryType') == 'TimelineTimelineItem':
                            tweet_results = content.get('itemContent', {}).get('tweet_results', {})
                            if tweet_results:
                                tweet = tweet_results.get('result', {})
                                if tweet and 'rest_id' in tweet:
                                    # Проверяем, что у твита есть legacy с full_text
                                    legacy = tweet.get('legacy', {})
                                    if legacy and 'full_text' in legacy:
                                        full_text = legacy['full_text']
                                        is_rt = full_text.startswith('RT @')
                                        
                                                                                # Сохраняем только нужные поля (по аналогии с reply)
                                        post_data = {
                                            'id': tweet['rest_id'],
                                            'full_text': full_text,
                                            'is_rt': is_rt,
                                            'created_at': legacy.get('created_at', '')
                                        }
                                        posts.append(post_data)
                                        logger.debug(f"Добавлен пост: {post_data['id']} ({'репост' if is_rt else 'пост'})")
                    except Exception as e:
                        logger.debug(f"Ошибка при обработке entry: {e}")
                        continue
        
        logger.debug(f"Всего извлечено постов: {len(posts)}")
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении постов: {e}")
    
    return posts

# =============================================================================
# 💾 РАБОТА С ПОСЛЕДНИМИ ПОСТАМИ/РЕПОСТАМИ (INFO)
# =============================================================================
def load_info_history(username):
    path = os.path.join(DATA_DIR_INFO, f"{username}_info.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Ошибка при загрузке истории для {username}: {e}")
        return []

def save_info_history(username, data):
    os.makedirs(DATA_DIR_INFO, exist_ok=True)
    path = os.path.join(DATA_DIR_INFO, f"{username}_info.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка при сохранении истории для {username}: {e}")

def find_new_info_posts(old_posts, new_posts):
    """Сравнивает старые и новые посты по ID и возвращает только новые"""
    try:
        # Создаем множество ID старых постов для быстрого поиска
        old_ids = {p['id'] for p in old_posts if 'id' in p}
        # Находим новые посты (те, которых нет в истории)
        new_only = [p for p in new_posts if 'id' in p and p['id'] not in old_ids]
        
        logger.debug(f"Найдено {len(new_only)} новых постов")
        
        return new_only
        
    except Exception as e:
        logger.error(f"Ошибка при сравнении постов: {e}")
        return []

# =============================================================================
# 📤 ОТПРАВКА НОВЫХ ПОСТОВ/РЕПОСТОВ В DISCORD
# =============================================================================
def send_new_info_posts_to_discord(channel_id, username, new_posts):
    """Отправляет новые info посты в Discord канал"""
    try:
        # Проверяем, что канал ID валидный
        if not channel_id or not str(channel_id).isdigit():
            logger.warning(f"❌ Неверный ID канала: {channel_id}")
            return 0
        
        # Получаем канал
        channel = bot.get_channel(int(channel_id))
        if not channel:
            logger.warning(f"❌ Канал {channel_id} не найден")
            return 0
        
        posts_sent = 0
        
        for post in new_posts:
            try:
                post_id = post.get('id')
                is_rt = post.get('is_rt', False)
                
                if not post_id:
                    continue
                
                # Формируем сообщение
                tweet_url = f"https://x.com/{username}/status/{post_id}"
                if is_rt:
                    text = f"[New repost from @{username}]({tweet_url})"
                else:
                    text = f"[New post from @{username}]({tweet_url})"
                
                # Отправляем сообщение через asyncio.run_coroutine_threadsafe
                asyncio.run_coroutine_threadsafe(
                    channel.send(text),
                    bot.loop
                )
                posts_sent += 1
                
                # Логируем успешную отправку
                if is_rt:
                    logger.success(f"✅ Repost @{username} отправлен в канал {channel_id}")
                else:
                    logger.success(f"✅ Post @{username} отправлен в канал {channel_id}")
                
                # Небольшая задержка между сообщениями
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке поста {post.get('id', 'unknown')} @{username} в Discord: {e}")
                continue
        
        return posts_sent
        
    except Exception as e:
        logger.error(f"❌ Ошибка в send_new_info_posts_to_discord: {e}")
        return 0

def cleanup_old_new_files():
    """Очищает все старые файлы new_* в начале нового запуска бота"""
    try:
        # Очищаем папку new_info
        if os.path.exists(NEW_DIR_INFO):
            for filename in os.listdir(NEW_DIR_INFO):
                if filename.startswith('new_') and filename.endswith('.json'):
                    file_path = os.path.join(NEW_DIR_INFO, filename)
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
        
        # Очищаем папку new_replies
        if os.path.exists(NEW_DIR_REPLY):
            for filename in os.listdir(NEW_DIR_REPLY):
                if filename.startswith('new_') and filename.endswith('.json'):
                    file_path = os.path.join(NEW_DIR_REPLY, filename)
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
        
        # Очищаем папку new_big
        if os.path.exists(NEW_DIR_BIG):
            for filename in os.listdir(NEW_DIR_BIG):
                if filename.startswith('new_') and filename.endswith('.json'):
                    file_path = os.path.join(NEW_DIR_BIG, filename)
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
        
        # Очищаем папку new (подписки)
        if os.path.exists(NEW_DIR):
            for channel_id in os.listdir(NEW_DIR):
                channel_dir = os.path.join(NEW_DIR, channel_id)
                if os.path.isdir(channel_dir):
                    for filename in os.listdir(channel_dir):
                        if filename.startswith('new_') and filename.endswith('.json'):
                            file_path = os.path.join(channel_dir, filename)
                            try:
                                os.remove(file_path)
                            except Exception:
                                pass
    except Exception:
        pass

# =============================================================================
# 🔍 СКАНИРОВАНИЕ INFO КАНАЛОВ
# =============================================================================

# --- Функции для работы с хранилищем info (перемещены выше для доступности) ---
def ensure_info_storage_exists():
    os.makedirs(DATA_DIR_INFO, exist_ok=True)
    if not os.path.exists(INFO_CHANNELS_FILE):
        try:
            with open(INFO_CHANNELS_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            logger.debug(f"Создан файл {INFO_CHANNELS_FILE}")
        except Exception as e:
            logger.error(f"Ошибка при создании файла {INFO_CHANNELS_FILE}: {e}")

def load_info_targets_for_channel(channel_id):
    # Читаем список пользователей из txt-файла
    txt_path = os.path.join(DATA_DIR_INFO, f"info_{channel_id}.txt")
    
    # Логируем попытку чтения
    logger.debug(f"load_info_targets_for_channel: канал ID {channel_id}")
    logger.debug(f"Путь к файлу: {txt_path}")
    logger.debug(f"Файл существует: {os.path.exists(txt_path)}")
    
    if not os.path.exists(txt_path):
        logger.debug("Файл не найден, возвращаем пустой список")
        return []
    
    targets = []
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    targets.append(line)
        
        # Логируем результат
        logger.debug(f"Прочитано таргетов: {len(targets)}")
        logger.debug(f"Список таргетов: {targets}")
            
    except Exception as e:
        logger.error(f"Ошибка при чтении {txt_path}: {e}")
        return []
    
    return targets

def save_info_targets_for_channel(channel_id, targets):
    # Обновляем txt-файл со списком пользователей
    txt_path = os.path.join(DATA_DIR_INFO, f"info_{channel_id}.txt")
    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("# Список пользователей для отслеживания info\n")
            f.write("# Каждый пользователь на новой строке\n")
            for t in targets:
                f.write(f"{t}\n")
        logger.debug(f"Сохранен список {len(targets)} таргетов в {txt_path}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении {txt_path}: {e}")
        return
    
    # Также обновляем JSON-файл для совместимости
    ensure_info_storage_exists()
    try:
        with open(INFO_CHANNELS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при чтении {INFO_CHANNELS_FILE}: {e}")
        data = {}
    
    data[str(channel_id)] = targets
    try:
        with open(INFO_CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Обновлен {INFO_CHANNELS_FILE} для канала {channel_id}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении {INFO_CHANNELS_FILE}: {e}")
# --- КОНЕЦ функций для работы с хранилищем info ---

def scan_info_targets():
    """Сканирует все info каналы для получения последних постов/репостов (по аналогии с scan_replies)"""
    try:
        os.makedirs(DATA_DIR_INFO, exist_ok=True)
        os.makedirs(NEW_DIR_INFO, exist_ok=True)
        

        
        # Собираем все файлы info_{channel_id}.txt
        info_files = [f for f in os.listdir(DATA_DIR_INFO) if f.startswith('info_') and f.endswith('.txt')]
        if not info_files:
            logger.warning("Нет info каналов для сканирования")
            return
        
        logger.info(f"Сканируем {len(info_files)} info каналов...")
        
        # Для каждого info канала
        for info_file in info_files:
            try:
                channel_id = info_file[len('info_'):-len('.txt')]
                logger.info(f"Обрабатываем канал {channel_id}...")
                
                # Загружаем таргеты для канала
                targets = load_info_targets_for_channel(channel_id)
                if not targets:
                    logger.info(f"В канале {channel_id} нет таргетов, пропускаем")
                    continue
                
                logger.info(f"Обрабатываем {len(targets)} таргетов в канале {channel_id}")
                
                # Для каждого таргета в канале
                for username in targets:
                    try:
                        if not is_valid_twitter_username(username):
                            logger.warning(f"Пропускаем невалидный username: {username}")
                            continue
                        
                        logger.debug(f"Обрабатываем таргет: {username}")
                        
                        # Получаем user_id
                        user_id = get_id(username, TWITTER_COOKIES, headers_id, params_id)
                        if not user_id:
                            logger.error(f'Ошибка при получении user_id для {username}')
                            continue
                        
                        # Получаем последние посты/репосты
                        info_json = get_latest_info(user_id, username, cookies_info, headers_info, params_info)
                        if not info_json:
                            logger.error(f'Ошибка при получении info для {username}')
                            continue
                        
                        # Извлекаем посты из JSON
                        new_posts = extract_posts_from_info(info_json)
                        if not new_posts:
                            logger.warning(f'Посты не найдены в ответе для {username}')
                            continue
                        
                        logger.debug(f"Получено {len(new_posts)} постов для {username}")
                        
                        # Загружаем историю постов
                        old_posts = load_info_history(username)
                        
                        if not old_posts:
                            # Первый запуск для таргета - сохраняем все посты как базовую линию, НЕ отправляем в Discord
                            save_info_history(username, new_posts)
                            logger.info(f'Первый запуск для {username}, сохранено {len(new_posts)} постов как базовая линия (НЕ отправляем в Discord)')
                            continue
                        
                        # Находим новые посты
                        new_only = find_new_info_posts(old_posts, new_posts)
                        
                        if new_only:
                            logger.info(f'Найдено {len(new_only)} новых постов для {username}')
                            
                            # Сохраняем новые посты в файл new_info для другого бота
                            try:
                                new_info_path = os.path.join(NEW_DIR_INFO, f'new_{username}_info.json')
                                save_json(new_only, new_info_path)
                                logger.success(f'💾 Новые посты сохранены в файл: {new_info_path}')
                            except Exception as e:
                                logger.error(f'Ошибка при сохранении новых постов в файл: {e}')
                            
                            # Отправляем новые посты в Discord
                            try:
                                logger.debug(f"Попытка отправки {len(new_only)} постов в канал {channel_id}")
                                posts_sent = send_new_info_posts_to_discord(channel_id, username, new_only)
                                logger.success(f'Отправлено {posts_sent}/{len(new_only)} постов в Discord канал {channel_id}')
                                

                                
                            except Exception as e:
                                logger.error(f'Ошибка при отправке постов в Discord: {e}')
                        else:
                            logger.debug(f'Новых постов для {username} не найдено')
                        
                        # Обновляем историю постов
                        save_info_history(username, new_posts)
                        logger.debug(f'История обновлена для {username}')
                        
                    except Exception as e:
                        logger.error(f"Ошибка при обработке таргета {username}: {e}")
                        continue
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке канала {channel_id}: {e}")
                continue
        
        logger.success(f"Сканирование info каналов завершено")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при сканировании info каналов: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

# =============================================================================
# 🔄 ОСНОВНАЯ ФУНКЦИЯ СКАНИРОВАНИЯ
# =============================================================================
def scan():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(NEW_DIR, exist_ok=True)
    
    # Очищаем все старые файлы new_* в начале нового запуска
    cleanup_old_new_files()
    
    channels = get_all_channels()
    if not channels:
        logger.error("Нет настроенных каналов в diff_chats.json")
        return
    
    logger.info(f"🔍 Начинаем сканирование для {len(channels)} каналов")
    for channel_id, targets in channels.items():
        logger.debug(f"  📺 Канал {channel_id}: {len(targets)} таргетов")
    
    checked_targets = set()
    for channel_id, targets in channels.items():
        channel_dir = os.path.join(NEW_DIR, str(channel_id))
        os.makedirs(channel_dir, exist_ok=True)
        logger.info(f"📺 Обрабатываем канал {channel_id} с {len(targets)} таргетами")
        for username in targets:
            if username in checked_targets:
                logger.info(f"⏭️ {username} уже был проверен, пропускаем для канала {channel_id}")
                continue
            checked_targets.add(username)
            logger.info(f"📡 Сканируем канал {channel_id} ({len(targets)} целей)")
            logger.info(f'🔍 Сканируем подписки пользователя: {username}')
            user_id = get_id(username, TWITTER_COOKIES, headers_id, params_id)
            if not user_id:
                logger.error(f'❌ Ошибка при получении user_id для {username}')
                continue
            followings = get_following(user_id, username, cookies_following, headers_following, params_following)
            if not followings:
                logger.error(f'❌ Ошибка при получении подписок для {username}')
                continue
            data_path = os.path.join(DATA_DIR, f'{username}.json')
            old_followings = load_json(data_path)
            if not old_followings:
                # Первый запуск для таргета - сохраняем все подписки как базовую линию, НЕ отправляем в Discord
                save_json(followings, data_path)
                logger.success(f'✅ Первый запуск для {username}, сохранено {len(followings)} подписок как базовая линия (НЕ отправляем в Discord)')
                # Удаляем старый файл new_ если он существует
                old_new_path = os.path.join(channel_dir, f'new_{username}.json')
                if os.path.exists(old_new_path):
                    os.remove(old_new_path)
                    logger.info(f'🗑️ Удален старый файл {old_new_path}')
                continue
            
            # Находим только новые подписки (те, которых не было в предыдущем сканировании)
            new_users = find_new_followings(old_followings, followings)
            if new_users:
                new_path = os.path.join(channel_dir, f'new_{username}.json')
                save_json(new_users, new_path)
                logger.success(f'🎯 Найдено {len(new_users)} новых подписок для {username} (канал {channel_id})')
            else:
                logger.info(f'⏭️ Новых подписок для {username} не найдено')
                # Удаляем старый файл new_ если он существует
                old_new_path = os.path.join(channel_dir, f'new_{username}.json')
                if os.path.exists(old_new_path):
                    os.remove(old_new_path)
                    logger.info(f'🗑️ Удален старый файл {old_new_path}')
            
            # Обновляем сохранённые данные для следующего сравнения
            save_json(followings, data_path)
    
    logger.info("📤 Завершено сканирование подписок, начинаем отправку в Discord")
    
    logger.info("📤 Отправляем новые подписки в Discord...")
    send_new_subscriptions_to_discord()
    logger.success("✅ Отправка в Discord завершена")
    
    # Добавляем сканирование больших подписчиков
    logger.scan_start("больших подписчиков")
    scan_big_followers()
    
    # Добавляем сканирование ответов
    logger.scan_start("ответов")
    scan_replies()
 
    # Добавляем сканирование info (последних постов/репостов)
    logger.scan_start("info (последних постов/репостов)")
    scan_info_targets()
    
    logger.info("🎯 Все модули сканирования завершены")
    logger.success("✅ Полный цикл сканирования завершен успешно")
    
    # Логирование завершено (Telegram модуль удален)
    logger.info("📊 Сканирование завершено - логи сохранены в файл")
 
# =============================================================================
# 📤 ОТПРАВКА НОВЫХ ПОДПИСОК В DISCORD
# =============================================================================
def send_new_subscriptions_to_discord():
    global bot_ready
    if not wait_for_discord_ready(timeout=30):
        logger.warning("❌ Discord бот не готов, пропускаем отправку подписок")
        return
    
    logger.info("Начинаем отправку новых подписок в Discord")
    
    files_processed = 0
    logger.info(f"🔍 Проверяем папку {NEW_DIR} на новые файлы...")
    for channel_id in os.listdir(NEW_DIR):
        channel_dir = os.path.join(NEW_DIR, channel_id)
        if not os.path.isdir(channel_dir):
            continue
        for filename in os.listdir(channel_dir):
            if not filename.endswith('.json') or filename.startswith('.'):
                continue
            filepath = os.path.join(channel_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    users = json.load(f)
                if not users or len(users) == 0:
                    logger.warning(f"⚠️ Файл {filename} пустой, пропускаем и удаляем")
                    # Удаляем пустой файл
                    try:
                        os.remove(filepath)
                        logger.debug(f"Пустой файл {filename} удален")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении пустого файла {filename}: {e}")
                    continue
                
                found_by = filename.replace('new_', '').replace('.json', '')
                channel_id_for_discord = int(channel_id)
                
                # Проверяем, что канал существует и доступен
                if not bot.get_channel(channel_id_for_discord):
                    logger.warning(f"❌ Канал {channel_id_for_discord} не найден, пропускаем файл {filename}")
                    continue
                
                logger.info(f"📤 Отправляем {len(users)} новых подписок от @{found_by} в канал {channel_id_for_discord}...")
                for i, user_data in enumerate(users, 1):
                    avatar_url = user_data[0]
                    created_at = user_data[1]
                    username = user_data[2]
                    name = user_data[3]
                    bio = user_data[4]
                    followers = user_data[5]
                    banner = user_data[6]
                    logger.debug(f"  📨 Отправляем {i}/{len(users)}: @{username} в канал {channel_id_for_discord}")
                    # Отправляем в Discord через asyncio.run_coroutine_threadsafe
                    try:
                        asyncio.run_coroutine_threadsafe(
                            send_discord(username, bio, name, avatar_url, found_by, channel_id_for_discord, followers, created_at, banner),
                            bot.loop
                        )
                    except Exception as e:
                        logger.error(f"Ошибка при отправке @{username}: {e}")
                    time.sleep(0.5)
                logger.success(f"✅ Отправлено: {filename}")
                files_processed += 1
            except Exception as e:
                logger.error(f"❌ Ошибка при обработке {filename}: {e}")
    logger.info(f"🎯 Обработано файлов: {files_processed}")

# =============================================================================
# 💬 REPLY МОДУЛЬ - ФУНКЦИИ ДЛЯ РАБОТЫ С ОТВЕТАМИ
# =============================================================================
def get_replies(user_id_reply, username_reply, cookies_reply, headers_reply, params_reply):
    try:
        headers = headers_reply.copy()
        params = params_reply.copy()
        headers['referer'] = f'https://x.com/{username_reply}/with_replies'
        params['variables'] = json.dumps({"userId": user_id_reply, "count": 20, "includePromotedContent": True, "withCommunity": True, "withVoice": True})
        url = "https://x.com/i/api/graphql/Ahzvm-qAUpVJN3-Ewy6rEw/UserTweetsAndReplies"
        print(f"[get_replies] user_id_reply={user_id_reply}, username_reply={username_reply}")
        print(f"[get_replies] url={url}")
        print(f"[get_replies] params={params}")
        print(f"[get_replies] headers={headers}")
        print(f"[get_replies] cookies={cookies_reply}")
        response = requests.get(url, params=params, cookies=cookies_reply, headers=headers)
        if response.status_code == 200:
            try:
                instructions = response.json()['data']['user']['result']['timeline']['timeline']['instructions']
            except Exception as e:
                print(f'[get_replies] Ошибка при парсинге ответов: {e}')
                return []
            replies = []
            def get_tweet_author_screen_name(tweet_obj):
                try:
                    user_result = (tweet_obj.get('core', {}).get('user_results', {}).get('result', {}))
                    name = (user_result.get('legacy', {}).get('screen_name') or user_result.get('core', {}).get('screen_name') or user_result.get('screen_name'))
                    return (name or "").lower()
                except Exception:
                    return ""
            for instr in instructions:
                if isinstance(instr, dict) and instr.get('type') == 'TimelineAddEntries':
                    for entry in instr.get('entries', []):
                        content = entry.get('content', {})
                        if content.get('entryType') == 'TimelineTimelineItem':
                            try:
                                tweet = content['itemContent']['tweet_results']['result']
                                legacy = tweet.get('legacy', {}) or {}
                                author_screen = get_tweet_author_screen_name(tweet)
                                if author_screen != (username_reply or "").lower():
                                    continue
                                if 'in_reply_to_screen_name' in legacy:
                                    reply_text = legacy.get('full_text', '')
                                    replied_to = legacy.get('in_reply_to_screen_name', '')
                                    original_tweet_id = legacy.get('in_reply_to_status_id_str', '')
                                    reply_id = legacy.get('id_str', '')
                                    created_at = legacy.get('created_at', '')
                                    replies.append({'reply_text': reply_text, 'replied_to': replied_to, 'original_tweet_id': original_tweet_id, 'reply_id': reply_id, 'created_at': created_at})
                            except Exception:
                                continue
                        elif content.get('entryType') == 'TimelineTimelineModule':
                            try:
                                items = content.get('items', [])
                                for item in items:
                                    if 'item' in item and 'itemContent' in item['item']:
                                        item_content = item['item']['itemContent']
                                        if item_content.get('itemType') == 'TimelineTweet':
                                            tweet = item_content['tweet_results']['result']
                                            legacy = tweet.get('legacy', {}) or {}
                                            author_screen = get_tweet_author_screen_name(tweet)
                                            if author_screen != (username_reply or "").lower():
                                                continue
                                            if 'in_reply_to_screen_name' in legacy:
                                                reply_text = legacy.get('full_text', '')
                                                replied_to = legacy.get('in_reply_to_screen_name', '')
                                                original_tweet_id = legacy.get('in_reply_to_status_id_str', '')
                                                reply_id = legacy.get('id_str', '')
                                                created_at = legacy.get('created_at', '')
                                                replies.append({'reply_text': reply_text, 'replied_to': replied_to, 'original_tweet_id': original_tweet_id, 'reply_id': reply_id, 'created_at': created_at})
                            except Exception:
                                continue
            return replies
        else:
            print(f'[get_replies] Ошибка при запросе ответов: {response.status_code}, {response.text}')
            return []
    except Exception as e:
        print(f'[get_replies] Общая ошибка при получении ответов: {e}')
        return []


def find_new_replies(old_replies, new_replies):
    if not old_replies:
        return new_replies
    old_reply_ids = {reply['reply_id'] for reply in old_replies}
    return [reply for reply in new_replies if reply['reply_id'] not in old_reply_ids]


def scan_replies():
    os.makedirs(DATA_DIR_REPLY, exist_ok=True)
    os.makedirs(NEW_DIR_REPLY, exist_ok=True)
    reply_files = [f for f in os.listdir(DATA_DIR_REPLY) if f.startswith('reply_') and f.endswith('.txt')]
    if not reply_files:
        try:
            from pathlib import Path
            global_path = os.path.join(DATA_DIR_REPLY, 'reply.txt')
            if Path(global_path).exists():
                with open(global_path, 'r', encoding='utf-8') as f:
                    targets = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            else:
                targets = []
        except Exception as e:
            print(f"[scan_replies] ❌ Ошибка при загрузке старого глобального списка reply: {e}")
            targets = []
        if not targets:
            print("[scan_replies] ❌ Нет пользователей для отслеживания ответов")
            return
        print(f"[scan_replies] 📡 Сканируем ответы {len(targets)} пользователей (глобальный режим)...")
        for username_reply in targets:
            if not is_valid_twitter_username(username_reply) or username_reply == '1404129636224602312':
                continue
            print(f'[scan_replies] 🔍 Сканируем ответы пользователя: {username_reply}')
            user_id_reply = get_id(username_reply, TWITTER_COOKIES, headers_id, params_id)
            if not user_id_reply:
                print(f'[scan_replies] ❌ Ошибка при получении user_id для {username_reply}')
                continue
            replies = get_replies(user_id_reply, username_reply, cookies_reply, headers_reply, params_reply)
            if not replies:
                print(f'[scan_replies] ❌ Ошибка при получении ответов для {username_reply}')
                continue
            data_path = os.path.join(DATA_DIR_REPLY, f'{username_reply}_replies.json')
            old_replies = load_json(data_path)
            if not old_replies:
                save_json(replies, data_path)
                print(f'[scan_replies] ✅ Первый запуск для {username_reply}, сохранено {len(replies)} ответов')
                continue
            new_replies = find_new_replies(old_replies, replies)
            if new_replies:
                new_path = os.path.join(NEW_DIR_REPLY, f'new_{username_reply}_replies.json')
                save_json(new_replies, new_path)
                print(f'[scan_replies] 🎯 Найдено {len(new_replies)} новых ответов для {username_reply}')
            else:
                print(f'[scan_replies] ⏭️ Новых ответов для {username_reply} не найдено')
            save_json(replies, data_path)
        print("[scan_replies] 📤 Отправляем новые ответы в Discord...")
        send_new_replies_to_discord()
        print("[scan_replies] ✅ Отправка ответов в Discord завершена")
        return
    for reply_file in reply_files:
        channel_id = reply_file[len('reply_'):-len('.txt')]
        targets = load_reply_targets(channel_id)
        if not targets:
            continue
        print(f"[scan_replies] 📡 Сканируем ответы {len(targets)} пользователей для канала {channel_id}...")
        for username_reply in targets:
            if not is_valid_twitter_username(username_reply) or username_reply == '1404129636224602312':
                continue
            print(f'[scan_replies] 🔍 Сканируем ответы пользователя: {username_reply}')
            user_id_reply = get_id(username_reply, TWITTER_COOKIES, headers_id, params_id)
            if not user_id_reply:
                print(f'[scan_replies] ❌ Ошибка при получении user_id для {username_reply}')
                continue
            replies = get_replies(user_id_reply, username_reply, cookies_reply, headers_reply, params_reply)
            if not replies:
                print(f'[scan_replies] ❌ Ошибка при получении ответов для {username_reply}')
                continue
            data_path = os.path.join(DATA_DIR_REPLY, f'{username_reply}_replies.json')
            old_replies = load_json(data_path)
            if not old_replies:
                save_json(replies, data_path)
                print(f'[scan_replies] ✅ Первый запуск для {username_reply}, сохранено {len(replies)} ответов')
                continue
            new_replies = find_new_replies(old_replies, replies)
            if new_replies:
                new_path = os.path.join(NEW_DIR_REPLY, f'new_{username_reply}_replies.json')
                save_json(new_replies, new_path)
                print(f'[scan_replies] 🎯 Найдено {len(new_replies)} новых ответов для {username_reply}')
            else:
                print(f'[scan_replies] ⏭️ Новых ответов для {username_reply} не найдено')
            save_json(replies, data_path)
    print("[scan_replies] 📤 Отправляем новые ответы в Discord...")
    send_new_replies_to_discord()
    print("[scan_replies] ✅ Отправка ответов в Discord завершена")

# =============================================================================
# 📤 ОТПРАВКА ОТВЕТОВ В DISCORD
# =============================================================================

def send_new_replies_to_discord():
    # Для каждого канала ищем свой файл с таргетами
    for filename in os.listdir(DATA_DIR_REPLY):
        if not filename.startswith("reply_") or not filename.endswith(".txt"):
            continue
        channel_id = filename[len("reply_"):-len(".txt")]
        try:
            targets = load_reply_targets(channel_id)
            if not targets:
                continue
            for username in targets:
                if not is_valid_twitter_username(username) or username == '1404129636224602312':
                    continue
                new_reply_path = os.path.join(NEW_DIR_REPLY, f"new_{username}_replies.json")
                if not os.path.exists(new_reply_path):
                    continue
                try:
                    with open(new_reply_path, 'r', encoding='utf-8') as f:
                        replies = json.load(f)
                    
                    if not replies:
                        # Удаляем пустой файл
                        try:
                            os.remove(new_reply_path)
                            logger.debug(f"Пустой файл {new_reply_path} удален")
                        except Exception as e:
                            logger.error(f"Ошибка при удалении пустого файла {new_reply_path}: {e}")
                        continue
                        
                    for reply_data in replies:
                        reply_text = reply_data['reply_text']
                        replied_to = reply_data['replied_to']
                        reply_id = reply_data['reply_id']
                        created_at = reply_data.get('created_at', '')
                        # Отправляем reply в Discord через asyncio.run_coroutine_threadsafe
                        try:
                            asyncio.run_coroutine_threadsafe(
                                send_reply_discord_to_channel(username, reply_text, replied_to, reply_id, created_at, channel_id),
                                bot.loop
                            )
                        except Exception as e:
                            logger.error(f"Ошибка при отправке reply для @{username}: {e}")
                        time.sleep(0.5)
                    

                        
                except Exception as e:
                    logger.error(f"Ошибка при чтении файла {new_reply_path}: {e}")
                    continue
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке reply для канала {channel_id}: {e}")

# =============================================================================
# ✅ ФУНКЦИИ ВАЛИДАЦИИ
# =============================================================================

def is_valid_twitter_username(username):
    return bool(re.match(r'^[A-Za-z0-9_]{1,15}$', username))

async def send_reply_discord_to_channel(username, reply_text, replied_to, reply_id, created_at, channel_id):
    try:
        if not is_valid_twitter_username(username) or username == '1404129636224602312':
            logger.info(f"⏭️ Пропуск невалидного username: {username}")
            return
        channel = bot.get_channel(int(channel_id))
        if not channel:
            logger.warning(f"❌ Канал {channel_id} не найден для отправки reply")
            return
        tweet_url = f"https://x.com/{username}/status/{reply_id}"
        msg = f"[Reply from {username}]({tweet_url})"
        await channel.send(msg)
        logger.success(f"✅ Reply @{username} отправлен в канал {channel_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке reply в канал {channel_id}: {e}")

# =============================================================================
# 🐦 TWITTER API ФУНКЦИИ
# =============================================================================
def get_id(name_user, cookies_id, headers_id, params_id):
    headers = headers_id.copy()
    params = params_id.copy()
    headers['referer'] = f'https://x.com/{name_user}/following'
    params['variables'] = json.dumps({"screen_name": name_user})
    url = "https://x.com/i/api/graphql/x3RLKWW1Tl7JgU7YtGxuzw/UserByScreenName"
    response = requests.get(url, params=params, cookies=cookies_id, headers=headers)
    if response.status_code == 200:
        try:
            data = response.json()
            if 'data' in data and 'user' in data['data'] and data['data']['user'] and 'result' in data['data']['user'] and data['data']['user']['result']:
                return data['data']['user']['result']['rest_id']
            else:
                logger.error(f'Пользователь {name_user} не найден или заблокирован: {data}')
                return None
        except Exception as e:
            logger.error(f'Ошибка при парсинге user_id для {name_user}: {e}, {response.text}')
            return None
    else:
        logger.error(f'Ошибка при запросе user_id: {response.status_code}, {response.text}')
        return None

def get_following(user_id, name_user, cookies_following, headers_following, params_following):
    headers = headers_following.copy()
    params = params_following.copy()
    headers['referer'] = f'https://x.com/{name_user}/following'
    params['variables'] = json.dumps({"userId": user_id, "count": 20, "includePromotedContent": False})
    url = "https://x.com/i/api/graphql/uAvNrZNqQfWpTerfEDd4DA/Following"
    response = requests.get(url, params=params, cookies=cookies_following, headers=headers)
    if response.status_code == 200:
        try:
            instructions = response.json()['data']['user']['result']['timeline']['timeline']['instructions']
        except Exception as e:
            logger.error(f'Ошибка при парсинге подписок: {e}, {response.text}')
            return []
        users = []
        for instr in instructions:
            if isinstance(instr, dict) and instr.get('type') == 'TimelineAddEntries':
                for entry in instr.get('entries', []):
                    content = entry.get('content', {})
                    if content.get('entryType') == 'TimelineTimelineItem':
                        try:
                            user = content['itemContent']['user_results']['result']
                            core = user.get('core', {}) or {}
                            legacy = user.get('legacy', {}) or {}
                            avatar_url = user.get('avatar', {}).get('image_url', '')
                            created_at = core.get('created_at', '')
                            username = core.get('screen_name', "")
                            name = core.get('name', '')
                            bio = legacy.get('description', "")
                            followers = legacy.get('followers_count', "")
                            banner = legacy.get('profile_banner_url', "")
                            users.append([avatar_url, created_at, username, name, bio, followers, banner])
                        except Exception:
                            continue
        return users
    else:
        logger.error(f'Ошибка при запросе following: {response.status_code}, {response.text}')
        return []

def load_reply_targets(channel_id):
    path = os.path.join(DATA_DIR_REPLY, f"reply_{channel_id}.txt")
    try:
        if not os.path.exists(path):
            logger.debug(f"Файл {path} не найден, возвращаем пустой список")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            targets = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        logger.debug(f"Загружено {len(targets)} целей для reply из {path}")
        return targets
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке списка ответов для канала {channel_id}: {e}")
        return []

# =============================================================================
# 🎮 DISCORD КОМАНДЫ ДЛЯ REPLY МОДУЛЯ
# =============================================================================

@tree.command(name="targets_reply", description="Показать текущий список для отслеживания ответов в этом канале")
async def targets_reply_slash(interaction: discord.Interaction):
    # Проверяем, что канал находится в категории x2-replies
    if not interaction.channel or not interaction.channel.category or interaction.channel.category.name != "x2-replies":
        await interaction.response.send_message("❌ Команда доступна только в каналах категории x2-replies", ephemeral=True)
        return
    channel_id = interaction.channel_id
    targets = load_reply_targets(channel_id)
    if not targets:
        embed = discord.Embed(title="📝 Список для отслеживания ответов", description="Список пуст", color=0x808080)
    else:
        embed = discord.Embed(title=f"📝 Список для отслеживания ответов – {len(targets)}", description="\n".join(f"@{t}" for t in targets), color=0x00BFFF)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="add_reply", description="Добавить пользователя в список для отслеживания ответов в этом канале")
@app_commands.describe(username="Ник пользователя (без @)")
async def add_reply_target_slash(interaction: discord.Interaction, username: str):
    # Проверяем, что канал находится в категории x2-replies
    if not interaction.channel or not interaction.channel.category or interaction.channel.category.name != "x2-replies":
        await interaction.response.send_message("❌ Команда доступна только в каналах категории x2-replies", ephemeral=True)
        return
    channel_id = interaction.channel_id
    targets = load_reply_targets(channel_id)
    username = username.strip().lstrip('@')
    if not is_valid_twitter_username(username) or username == '1404129636224602312':
        await interaction.response.send_message(f"❌ Некорректный username: {username}", ephemeral=True)
        return
    if username in targets:
        await interaction.response.send_message(f"⚠️ @{username} уже есть в списке", ephemeral=True)
        return
    targets.append(username)
    path = os.path.join(DATA_DIR_REPLY, f"reply_{channel_id}.txt")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Список пользователей для отслеживания ответов\n")
            f.write("# Каждый пользователь на новой строке\n")
            for t in targets:
                f.write(f"{t}\n")
        logger.success(f"Добавлен @{username} в список reply для канала {channel_id}")
        await interaction.response.send_message(f"✅ @{username} добавлен в список для отслеживания ответов", ephemeral=True)
    except Exception as e:
        logger.error(f"Ошибка при сохранении списка reply для канала {channel_id}: {e}")
        await interaction.response.send_message(f"❌ Ошибка при сохранении списка", ephemeral=True)

@tree.command(name="remove_reply", description="Удалить пользователя из списка для отслеживания ответов в этом канале")
@app_commands.describe(username="Ник пользователя (без @)")
async def remove_reply_target_slash(interaction: discord.Interaction, username: str):
    # Проверяем, что канал находится в категории x2-replies
    if not interaction.channel or not interaction.channel.category or interaction.channel.category.name != "x2-replies":
        await interaction.response.send_message("❌ Команда доступна только в каналах категории x2-replies", ephemeral=True)
        return
    channel_id = interaction.channel_id
    targets = load_reply_targets(channel_id)
    username = username.strip().lstrip('@')
    if username not in targets:
        await interaction.response.send_message(f"⚠️ @{username} не найден в списке", ephemeral=True)
        return
    targets.remove(username)
    path = os.path.join(DATA_DIR_REPLY, f"reply_{channel_id}.txt")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Список пользователей для отслеживания ответов\n")
            f.write("# Каждый пользователь на новой строке\n")
            for t in targets:
                f.write(f"{t}\n")
        logger.success(f"Удален @{username} из списка reply для канала {channel_id}")
        await interaction.response.send_message(f"✅ @{username} удалён из списка для отслеживания ответов", ephemeral=True)
    except Exception as e:
        logger.error(f"Ошибка при сохранении списка reply для канала {channel_id}: {e}")
        await interaction.response.send_message(f"❌ Ошибка при сохранении списка", ephemeral=True)

# =============================================================================
# 🚀 ТОЧКА ВХОДА И ОСНОВНОЙ ЦИКЛ
# =============================================================================


def main_loop():
    """Основной цикл сканирования"""
    main_loop_running = True
    while main_loop_running:
        try:
            logger.session_separator()
            logger.info(f"🚀 НОВЫЙ ЗАПУСК СКАНИРОВАНИЯ - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.session_separator()
            logger.scan_start("основного модуля")
            logger.info(f"Начинаем сканирование... {time.strftime('%Y-%m-%d %H:%M:%S')}")
            scan()
            logger.scan_complete("основного модуля")
            logger.info("Сканирование завершено. Ожидаем 1 час...")
            logger.session_separator()
            logger.info(f"⏸️ ЦИКЛ ЗАВЕРШЕН - ОЖИДАНИЕ 1 ЧАС - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.session_separator()
            time.sleep(3600)  # 1 час = 3600 секунд
        except KeyboardInterrupt:
            logger.session_separator()
            logger.info("🛑 БОТ ОСТАНОВЛЕН ПОЛЬЗОВАТЕЛЕМ")
            logger.session_separator()
            main_loop_running = False
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")
            logger.info("⏳ Повторная попытка через 30 секунд...")
            time.sleep(30)  # Оставляем 30 секунд для повторных попыток при ошибках

if __name__ == "__main__":
    discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
    discord_thread.start()
    
    # Ждем готовности Discord бота
    if wait_for_discord_ready(timeout=30):
        logger.success("✅ Discord бот готов!")
        # Приветственное сообщение заменено на статус запуска в on_ready
    else:
        logger.warning("⚠️ Discord бот не готов, но продолжаем работу")
    
    # Запускаем основной цикл
    try:
        # Добавляем разделитель для первого запуска
        logger.session_separator()
        logger.info("🚀 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ")
        logger.session_separator()
        
        main_loop()
    except KeyboardInterrupt:
        logger.session_separator()
        logger.info("🛑 БОТ ОСТАНОВЛЕН ПОЛЬЗОВАТЕЛЕМ")
        logger.session_separator()
    except Exception as e:
        logger.session_separator()
        logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА В ОСНОВНОМ ЦИКЛЕ: {e}")
        logger.session_separator()

# Обрывок кода удален - все функции уже реализованы в основном коде

# Ограничение команд только для reply-каналов
REPLY_CATEGORY_NAME = "x2-replies"
@bot.check
async def only_reply_commands_in_reply_channels(ctx):
    if ctx.command is None:
        return True
    if hasattr(ctx.channel, 'category') and ctx.channel.category and ctx.channel.category.name == REPLY_CATEGORY_NAME:
        # Разрешены только команды reply
        return ctx.command.name in ["add_reply", "remove_reply", "list_reply"]
    return True

# =============================================================================
# 🔧 ФУНКЦИИ ДЛЯ РАБОТЫ С ХРАНИЛИЩЕМ INFO
# =============================================================================

# Глобальная инициализация хранилища info (как у last_reply)
try:
    os.makedirs(DATA_DIR_INFO, exist_ok=True)
    if not os.path.exists(INFO_CHANNELS_FILE):
        with open(INFO_CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        logger.debug(f"Инициализирован файл {INFO_CHANNELS_FILE}")
except Exception as e:
    logger.error(f"Ошибка при инициализации хранилища info: {e}")

# Канал, где размещается info-embed с кнопками create/delete (актуальный ID)
# INFO_PANEL_CHANNEL_ID уже определен выше на строке 74

# =============================================================================
# 🔴 TELEGRAM МОДУЛЬ: КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ INFO ТАРГЕТАМИ
# =============================================================================
# 🔴 TELEGRAM МОДУЛЬ ПОЛНОСТЬЮ УДАЛЕН
# =============================================================================


