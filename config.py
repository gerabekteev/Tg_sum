import json
import os
import platform
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Корневой путь проекта
BASE_DIR = Path(__file__).resolve().parent

# Папки для дампов сообщений и сессий Telegram
DUMPS_DIR = BASE_DIR / "dumps"
SESSIONS_DIR = BASE_DIR / "sessions"

# Создаем папки, если их нет
DUMPS_DIR.mkdir(exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)

# Чтение и валидация конфигурации из .env (статические значения)
try:
    API_ID_RAW = os.getenv("TELEGRAM_API_ID")
    API_ID = int(API_ID_RAW) if API_ID_RAW else 0
except ValueError:
    API_ID = 0

API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

try:
    ADMIN_ID_RAW = os.getenv("ADMIN_ID")
    ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW else 0
except ValueError:
    ADMIN_ID = 0

# Значения по умолчанию из .env (могут быть переопределены через бота)
_DEFAULT_TARGET_CHAT = os.getenv("TARGET_CHAT", "")
try:
    _DEFAULT_PERIOD_HOURS = int(os.getenv("DEFAULT_PERIOD_HOURS", "4"))
except ValueError:
    _DEFAULT_PERIOD_HOURS = 4

# Пути к сессиям и файлу динамических настроек
USER_SESSION_PATH = str(SESSIONS_DIR / "user_session")
BOT_SESSION_PATH = str(SESSIONS_DIR / "bot_session")
SETTINGS_FILE = SESSIONS_DIR / "settings.json"

# Путь к исполняемому файлу Antigravity CLI (agy)
# По умолчанию используется глобальная команда 'agy', доступная в системе
AGY_CLI_PATH = os.getenv("AGY_CLI_PATH", os.getenv("GEMINI_CLI_PATH", "agy"))


# Часовой пояс для работы с датами и временем
TIMEZONE_STR = os.getenv("TIMEZONE", "UTC")
try:
    TIMEZONE = ZoneInfo(TIMEZONE_STR)
except Exception:
    import datetime
    TIMEZONE = datetime.timezone.utc


# ─── Динамические настройки (управляются через бота) ───

def _load_settings() -> dict:
    """Загрузить динамические настройки из settings.json."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_settings(settings: dict):
    """Сохранить динамические настройки в settings.json."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def get_target_chat() -> str:
    """Получить текущий целевой чат (из settings.json или .env)."""
    settings = _load_settings()
    return settings.get("target_chat", _DEFAULT_TARGET_CHAT)

def set_target_chat(value: str):
    """Установить новый целевой чат и сохранить."""
    settings = _load_settings()
    settings["target_chat"] = value
    _save_settings(settings)

def get_period_hours() -> int:
    """Получить текущий период автосбора в часах."""
    settings = _load_settings()
    return settings.get("period_hours", _DEFAULT_PERIOD_HOURS)

def set_period_hours(value: int):
    """Установить новый период автосбора и сохранить."""
    settings = _load_settings()
    settings["period_hours"] = value
    _save_settings(settings)

# Обратная совместимость: модули, которые читают config.TARGET_CHAT напрямую
TARGET_CHAT = get_target_chat()
DEFAULT_PERIOD_HOURS = _DEFAULT_PERIOD_HOURS

def validate_config():
    """Простая проверка конфигурации на наличие заполненных заглушек."""
    errors = []
    if not API_ID:
        errors.append("TELEGRAM_API_ID не задан или некорректен.")
    if not API_HASH or API_HASH == "your_api_hash_here":
        errors.append("TELEGRAM_API_HASH не задан.")
    if not BOT_TOKEN or "ABCdefGh" in BOT_TOKEN:
        errors.append("BOT_TOKEN не задан.")
    if not ADMIN_ID:
        errors.append("ADMIN_ID не задан.")
    return errors
