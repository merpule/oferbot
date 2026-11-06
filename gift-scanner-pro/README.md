# Gift Scanner Pro

Сканер Telegram NFT-подарков: FastAPI + SQLite, бот на aiogram 3, Mini App (HTML/JS).

## Как это работает
Основной источник — сам Telegram (Telethon, метод `payments.getUniqueStarGift`). Сканер перебирает номера
выбранной коллекции (`PlushPepe-1`, `PlushPepe-2`, …), сохраняет модель, фон, узор и владельца в SQLite.
Username показывается только если он публичный; иначе «Username не указан». Приватное не извлекается.
Portals (Partner API) подключён как отдельный адаптер. Getgems — **не реализован**.

## Установка
1. `python -m venv venv && source venv/bin/activate` (Windows: `venv\Scripts\activate`)
2. `pip install -r requirements.txt`
3. `cp .env.example .env` и заполни:
   - `BOT_TOKEN` — у @BotFather;
   - `TG_API_ID`, `TG_API_HASH` — https://my.telegram.org → API development tools;
   - `PORTALS_API_KEY` — мини-апп Portals → профиль → Partner API (ключ даёт и запись — не публикуй его);
   - `WEBAPP_URL` — публичный HTTPS-адрес backend (на хостинге с доменом или через ngrok/cloudflared);
   - `INTERNAL_SECRET` — любая длинная случайная строка.
4. Один раз: `python login.py` (телефон и код от Telegram — сессия сохранится в `data/`).
   Используй отдельный аккаунт, а не основной.
5. Backend: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
6. Бот (в другом окне): `python -m bot.bot`
7. В @BotFather: `/setmenubutton` или просто используй кнопку «Открыть сканер» из `/start`.

Локальная отладка без Telegram: `DEV_MODE=1`, открой http://127.0.0.1:8000.

## Чек-лист первого запуска (я не мог проверить это без интернета)
- [ ] Вкладка «Настройки»: Telegram-сканер «работает».
- [ ] Скан `PlushPepe` 1–20: поля модель/фон/узор заполнены. Если пусто — пришли лог/ответ, поправим парсер в `providers/tg_scan.py`.
- [ ] У части подарков есть @username, у скрытых — «Username не указан».
- [ ] Повторный скан того же диапазона берётся из кэша (счётчик «из кэша»).
- [ ] Фильтры и «Показать ещё» работают; число «уникальных владельцев» не дублирует людей.
- [ ] Картинки: адрес `nft.fragment.com/gift/<slug>.medium.jpg` не проверен; если не грузятся, карточка просто без картинки.
- [ ] Portals: `GET /api/portals/search` — имя заголовка ключа (`PORTALS_AUTH_HEADER`) и параметры сверь с OpenAPI Portals.

## Что не сделано / ограничения
- Getgems-адаптер не реализован (эндпоинты не проверены).
- Фильтр «есть объявление о продаже» не реализован: эти данные только в Portals, в общей базе их нет.
- Telegram ограничивает частоту (FloodWait). Большие коллекции сканируются долго; пауза — `SCAN_DELAY`.
- Список коллекций строится из уже просканированного (автокаталога всех коллекций нет).
- Боту доступны `/search`, `/favorites`, `/history` через общий backend; сканирование запускается в Mini App.
