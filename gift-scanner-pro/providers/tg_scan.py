"""Основной источник: Telegram (MTProto через Telethon).
Для каждого slug вида «PlushPepe-123» вызывается payments.getUniqueStarGift.
Поля ответа читаются осторожно (getattr): если Telegram поменяет схему, поле станет пустым,
а не уронит сканер. Username берётся только если он публично указан у владельца."""
import asyncio
from telethon import TelegramClient, errors
from telethon.tl.functions.payments import GetUniqueStarGiftRequest
from config.settings import settings
from providers.base import GiftMissing, ProviderUnavailable


class TgScanner:
    def __init__(self):
        self.client = None
        self.error = None

    async def start(self):
        if not (settings.TG_API_ID and settings.TG_API_HASH):
            self.error = "Не заданы TG_API_ID / TG_API_HASH в .env"
            return
        self.client = TelegramClient(settings.TG_SESSION, int(settings.TG_API_ID), settings.TG_API_HASH)
        await self.client.connect()
        if not await self.client.is_user_authorized():
            self.error = "Сессия не авторизована. Запусти: python login.py"
            await self.client.disconnect(); self.client = None

    async def stop(self):
        if self.client:
            await self.client.disconnect()

    @property
    def ready(self):
        return self.client is not None

    async def fetch(self, slug):
        if not self.client:
            raise ProviderUnavailable(self.error or "Telegram-сканер не запущен")
        while True:
            try:
                res = await self.client(GetUniqueStarGiftRequest(slug=slug))
                break
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds + 1)
            except errors.RPCError as e:
                msg = str(e).upper()
                if "SLUG" in msg or "NOT_FOUND" in msg or "INVALID" in msg:
                    raise GiftMissing(slug)
                raise
        g = getattr(res, "gift", None)
        if g is None:
            raise GiftMissing(slug)
        out = {"slug": slug, "collection": slug.rsplit("-", 1)[0], "num": int(slug.rsplit("-", 1)[1])}
        for a in getattr(g, "attributes", None) or []:
            kind = type(a).__name__
            name = getattr(a, "name", None)
            if kind.endswith("Model"): out["model"] = name
            elif kind.endswith("Backdrop"): out["backdrop"] = name
            elif kind.endswith("Pattern"): out["pattern"] = name
        peer = getattr(g, "owner_id", None)
        uid = getattr(peer, "user_id", None)
        out["owner_id"] = uid
        out["owner_name"] = getattr(g, "owner_name", None)
        for u in getattr(res, "users", None) or []:
            if uid is not None and getattr(u, "id", None) == uid:
                out["owner_username"] = getattr(u, "username", None)
                out["owner_name"] = out["owner_name"] or getattr(u, "first_name", None)
        return out
