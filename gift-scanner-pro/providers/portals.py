"""Portals Partner API (https://portal-market.com), метод GET /partners/nfts/search — только чтение.
ВАЖНО: имя заголовка авторизации и параметры поиска НЕ проверены вживую (в среде разработки не было сети).
Заголовок настраивается PORTALS_AUTH_HEADER, параметры передаются как есть из запроса.
Сверься с OpenAPI Portals и поправь при необходимости."""
import asyncio
import time
import httpx
from config.settings import settings
from providers.base import ProviderUnavailable

_last = 0.0
_lock = asyncio.Lock()


async def search(params: dict):
    global _last
    if not settings.PORTALS_API_KEY:
        raise ProviderUnavailable("PORTALS_API_KEY не задан в .env")
    async with _lock:  # ограничение частоты
        wait = 1.0 / settings.PORTALS_RPS - (time.monotonic() - _last)
        if wait > 0:
            await asyncio.sleep(wait)
        _last = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(settings.PORTALS_BASE_URL + "/partners/nfts/search", params=params,
                            headers={settings.PORTALS_AUTH_HEADER: settings.PORTALS_API_KEY})
    except httpx.HTTPError as e:
        raise ProviderUnavailable(f"Portals недоступен: {e}")
    if r.status_code in (401, 403):
        raise ProviderUnavailable("Portals отклонил ключ (401/403): проверь ключ и PORTALS_AUTH_HEADER")
    if r.status_code == 429:
        raise ProviderUnavailable("Portals: лимит запросов (429), попробуй позже")
    if r.status_code >= 400:
        raise ProviderUnavailable(f"Portals вернул {r.status_code}")
    return r.json()
