import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from config.settings import settings

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()


def kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть сканер", web_app=WebAppInfo(url=settings.WEBAPP_URL))]])


async def api(path, uid, **params):
    """Бот не содержит своей логики поиска — всё через общий backend."""
    async with httpx.AsyncClient(timeout=20, base_url=settings.BACKEND_URL) as c:
        r = await c.get(path, params=params, headers={"X-Bot-Secret": settings.INTERNAL_SECRET, "X-User-Id": str(uid)})
        r.raise_for_status()
        return r.json()


def line(g):
    owner = f"@{g['owner_username']}" if g.get("owner_username") else "Username не указан"
    return f"<a href=\"https://t.me/nft/{g['slug']}\">{g['slug']}</a> — {g.get('model') or '?'} / {g.get('backdrop') or '?'} / {g.get('pattern') or '?'} — {owner}"


async def safe(m: Message, coro):
    try:
        return await coro
    except Exception as e:  # noqa
        await m.answer(f"Backend недоступен: {e}")


@dp.message(Command("start"))
async def start(m: Message):
    await m.answer("Gift Scanner Pro ищет Telegram NFT-подарки и их публичных владельцев.\n"
                   "/scanner — открыть сканер\n/search — поиск\n/favorites — избранное\n/history — история\n/help — помощь",
                   reply_markup=kb())


@dp.message(Command("scanner"))
async def scanner(m: Message):
    await m.answer("Сканер:", reply_markup=kb())


@dp.message(Command("search"))
async def search(m: Message, command: CommandObject):
    if not command.args:
        return await m.answer("Напиши так: /search PlushPepe-1 или /search @username")
    d = await safe(m, api("/api/gifts", m.from_user.id, q=command.args, limit=10))
    if d is None:
        return
    items = d["items"]
    if not items:
        return await m.answer("Ничего не найдено в базе. Запусти сканирование этой коллекции в Mini App.")
    s = d["stats"]
    await m.answer(f"Найдено: {s['total']}, уникальных владельцев: {s['owners']}\n\n" + "\n".join(map(line, items)),
                   parse_mode="HTML", disable_web_page_preview=True)


@dp.message(Command("favorites"))
async def favorites(m: Message):
    items = await safe(m, api("/api/favorites", m.from_user.id))
    if items is not None:
        await m.answer("\n".join(map(line, items)) or "Избранное пусто", parse_mode="HTML", disable_web_page_preview=True)


@dp.message(Command("history"))
async def history(m: Message):
    items = await safe(m, api("/api/history", m.from_user.id))
    if items is not None:
        await m.answer("\n".join(i["query"] for i in items) or "История пуста")


@dp.message(Command("help"))
async def help_(m: Message):
    await m.answer("Сканер собирает данные по номерам коллекции (например PlushPepe 1–500) и сохраняет в базу. "
                   "Username виден, только если владелец сам сделал его публичным.", reply_markup=kb())


async def main():
    await Bot(settings.BOT_TOKEN).delete_webhook()
    await dp.start_polling(Bot(settings.BOT_TOKEN))

if __name__ == "__main__":
    asyncio.run(main())
