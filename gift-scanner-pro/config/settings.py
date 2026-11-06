import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    WEBAPP_URL = os.getenv("WEBAPP_URL", "")          # публичный https-адрес Mini App
    BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "change-me")
    DEV_MODE = os.getenv("DEV_MODE", "0") == "1"      # 1 = без проверки initData (только локально)
    DB_PATH = os.getenv("DB_PATH", "data/gifts.db")

    TG_API_ID = os.getenv("TG_API_ID", "")
    TG_API_HASH = os.getenv("TG_API_HASH", "")
    TG_SESSION = os.getenv("TG_SESSION", "data/scanner")

    SCAN_DELAY = float(os.getenv("SCAN_DELAY", "0.6"))        # пауза между запросами, сек
    CACHE_TTL = int(os.getenv("CACHE_TTL", "86400"))          # сколько хранить результат, сек
    STOP_AFTER_MISSING = int(os.getenv("STOP_AFTER_MISSING", "25"))

    PORTALS_API_KEY = os.getenv("PORTALS_API_KEY", "")
    PORTALS_BASE_URL = os.getenv("PORTALS_BASE_URL", "https://portal-market.com")
    PORTALS_AUTH_HEADER = os.getenv("PORTALS_AUTH_HEADER", "Authorization")
    PORTALS_RPS = float(os.getenv("PORTALS_RPS", "2"))


settings = Settings()
