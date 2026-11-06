import asyncio
import hashlib
import hmac
import json
import time
import uuid
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config.settings import settings
from database import db
from providers import getgems, portals
from providers.base import GiftMissing, ProviderUnavailable
from providers.tg_scan import TgScanner

scanner = TgScanner()
jobs: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app):
    await db.init()
    await scanner.start()
    yield
    await scanner.stop()


app = FastAPI(title="Gift Scanner Pro", lifespan=lifespan)


# ---------- авторизация ----------
def _check_init_data(init: str):
    d = dict(parse_qsl(init, keep_blank_values=True))
    h = d.pop("hash", None)
    if not h or not settings.BOT_TOKEN:
        return None
    s = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
    key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(key, s.encode(), hashlib.sha256).hexdigest(), h):
        return None
    if time.time() - int(d.get("auth_date", 0)) > 86400:
        return None
    return json.loads(d["user"])["id"]


async def user_id(x_init_data: str = Header(default=""), x_bot_secret: str = Header(default=""),
                  x_user_id: str = Header(default="")) -> int:
    if x_bot_secret and hmac.compare_digest(x_bot_secret, settings.INTERNAL_SECRET) and x_user_id.isdigit():
        return int(x_user_id)
    uid = _check_init_data(x_init_data) if x_init_data else None
    if uid is not None:
        return uid
    if settings.DEV_MODE:
        return 0
    raise HTTPException(401, "Открой приложение из Telegram")


# ---------- сканирование ----------
class ScanReq(BaseModel):
    collection: str = Field(pattern=r"^[A-Za-z0-9_]{2,64}$", description="Например PlushPepe")
    start: int = Field(ge=1, le=10_000_000)
    end: int = Field(ge=1, le=10_000_000)


async def run_job(job):
    consecutive_missing = consecutive_err = 0
    try:
        for n in range(job["start"], job["end"] + 1):
            if job["cancel"]:
                job["status"] = "cancelled"; return
            slug = f'{job["collection"]}-{n}'
            job["current"] = n
            if await db.is_fresh(slug):
                job["cached"] += 1; job["done"] += 1; consecutive_missing = 0
                continue
            try:
                g = await scanner.fetch(slug)
                await db.upsert(g)
                job["found"] += 1; consecutive_missing = consecutive_err = 0
            except GiftMissing:
                job["missing"] += 1; consecutive_missing += 1
                if consecutive_missing >= settings.STOP_AFTER_MISSING:
                    job["status"] = "finished"
                    job["note"] = f"Остановлено: {consecutive_missing} подряд несуществующих номеров — вероятно, конец тиража"
                    return
            except ProviderUnavailable as e:
                job["status"] = "error"; job["error"] = str(e); return
            except Exception as e:  # noqa
                consecutive_err += 1; job["errors"] += 1; job["last_error"] = repr(e)
                if consecutive_err >= 5:
                    job["status"] = "error"; job["error"] = f"5 ошибок подряд, последняя: {e!r}"; return
            job["done"] += 1
            await asyncio.sleep(settings.SCAN_DELAY)
        job["status"] = "finished"
    finally:
        job["running"] = False


@app.post("/api/scan")
async def scan_start(req: ScanReq, uid: int = Depends(user_id)):
    if req.end < req.start:
        raise HTTPException(422, "Конец диапазона меньше начала")
    if not scanner.ready:
        raise HTTPException(503, scanner.error or "Telegram-сканер не запущен")
    for j in jobs.values():  # защита от повторных запросов
        if j["running"] and j["collection"].lower() == req.collection.lower():
            return j
    job = dict(id=uuid.uuid4().hex[:8], collection=req.collection, start=req.start, end=req.end,
               total=req.end - req.start + 1, done=0, found=0, cached=0, missing=0, errors=0, current=req.start,
               status="running", running=True, cancel=False, error=None, note=None, last_error=None)
    jobs[job["id"]] = job
    await db.hist_add(uid, f"{req.collection} {req.start}-{req.end}")
    asyncio.create_task(run_job(job))
    return job


@app.get("/api/scan/{job_id}")
async def scan_status(job_id: str, uid: int = Depends(user_id)):
    if job_id not in jobs:
        raise HTTPException(404, "Задача не найдена")
    return jobs[job_id]


@app.post("/api/scan/{job_id}/cancel")
async def scan_cancel(job_id: str, uid: int = Depends(user_id)):
    if job_id not in jobs:
        raise HTTPException(404, "Задача не найдена")
    jobs[job_id]["cancel"] = True
    return {"ok": True}


# ---------- данные ----------
def _filters(collection=None, model=None, backdrop=None, pattern=None, number=None, owner=None, q=None):
    return dict(collection=collection, model=model, backdrop=backdrop, pattern=pattern,
                number=number, owner=owner, q=q)


@app.get("/api/gifts")
async def gifts(collection: str | None = None, model: str | None = None, backdrop: str | None = None,
                pattern: str | None = None, number: int | None = None, owner: str | None = None,
                q: str | None = None, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                uid: int = Depends(user_id)):
    f = _filters(collection, model, backdrop, pattern, number, owner, q)
    items = await db.gifts(f, limit, offset)
    for g in items:
        g["url"] = f"https://t.me/nft/{g['slug']}"
        g["image"] = f"https://nft.fragment.com/gift/{g['slug'].lower()}.medium.jpg"
    return {"items": items, "stats": await db.stats(f)}


@app.get("/api/facets/{kind}")
async def facets(kind: str, uid: int = Depends(user_id)):
    if kind not in db.FACETS:
        raise HTTPException(404, "Неизвестный каталог")
    return await db.facet(kind)


@app.get("/api/owners")
async def owners(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), uid: int = Depends(user_id)):
    return await db.owners(limit, offset)


@app.get("/api/favorites")
async def fav_get(uid: int = Depends(user_id)):
    return await db.fav_list(uid)


@app.put("/api/favorites/{slug}")
async def fav_put(slug: str, uid: int = Depends(user_id)):
    await db.fav_set(uid, slug, True); return {"ok": True}


@app.delete("/api/favorites/{slug}")
async def fav_del(slug: str, uid: int = Depends(user_id)):
    await db.fav_set(uid, slug, False); return {"ok": True}


@app.get("/api/history")
async def history(uid: int = Depends(user_id)):
    return await db.hist_list(uid)


@app.get("/api/portals/search")
async def portals_search(offset: int = 0, limit: int = Query(20, le=100), collection: str | None = None,
                         uid: int = Depends(user_id)):
    params = {"offset": offset, "limit": limit}
    if collection:
        params["collection"] = collection
    try:
        return await portals.search(params)
    except ProviderUnavailable as e:
        raise HTTPException(503, str(e))


@app.get("/api/status")
async def status(uid: int = Depends(user_id)):
    return {
        "telegram_scanner": {"ready": scanner.ready, "error": scanner.error},
        "portals": {"ready": bool(settings.PORTALS_API_KEY),
                    "note": None if settings.PORTALS_API_KEY else "PORTALS_API_KEY не задан"},
        "getgems": {"ready": getgems.AVAILABLE, "note": getgems.REASON},
    }


@app.get("/")
async def index():
    return FileResponse("frontend/index.html")


app.mount("/static", StaticFiles(directory="frontend"), name="static")
