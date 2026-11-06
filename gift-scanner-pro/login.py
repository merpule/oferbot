"""Одноразовая авторизация сканера в Telegram: python login.py"""
import asyncio
from telethon import TelegramClient
from config.settings import settings


async def main():
    c = TelegramClient(settings.TG_SESSION, int(settings.TG_API_ID), settings.TG_API_HASH)
    await c.start()  # спросит телефон и код
    me = await c.get_me()
    print("Готово, вошли как", me.first_name)
    await c.disconnect()

asyncio.run(main())
