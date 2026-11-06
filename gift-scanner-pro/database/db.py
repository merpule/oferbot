import time
import aiosqlite
from config.settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS gifts(
  slug TEXT PRIMARY KEY, collection TEXT, num INTEGER, model TEXT, backdrop TEXT, pattern TEXT,
  owner_id INTEGER, owner_username TEXT, owner_name TEXT, scanned_at INTEGER);
CREATE INDEX IF NOT EXISTS ix_gifts_col ON gifts(collection);
CREATE INDEX IF NOT EXISTS ix_gifts_owner ON gifts(owner_username);
CREATE TABLE IF NOT EXISTS favorites(user_id INTEGER, slug TEXT, PRIMARY KEY(user_id, slug));
CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, query TEXT, created_at INTEGER);
"""

FACETS = {"collection", "model", "backdrop", "pattern"}


async def init():
    async with aiosqlite.connect(settings.DB_PATH) as c:
        await c.executescript(SCHEMA)
        await c.commit()


def _where(f):
    cond, params = [], []
    for k in FACETS:
        if f.get(k):
            cond.append(f"{k}=? COLLATE NOCASE"); params.append(f[k])
    if f.get("number") is not None:
        cond.append("num=?"); params.append(f["number"])
    if f.get("owner"):
        cond.append("owner_username LIKE ?"); params.append("%" + f["owner"].lstrip("@") + "%")
    if f.get("q"):
        like = "%" + f["q"].lstrip("@") + "%"
        cond.append("(slug LIKE ? OR collection LIKE ? OR owner_username LIKE ?)"); params += [like] * 3
    return (" WHERE " + " AND ".join(cond)) if cond else "", params


async def upsert(g):
    async with aiosqlite.connect(settings.DB_PATH) as c:
        await c.execute(
            "INSERT OR REPLACE INTO gifts VALUES(?,?,?,?,?,?,?,?,?,?)",
            (g["slug"], g["collection"], g["num"], g.get("model"), g.get("backdrop"), g.get("pattern"),
             g.get("owner_id"), g.get("owner_username"), g.get("owner_name"), int(time.time())))
        await c.commit()


async def is_fresh(slug):
    async with aiosqlite.connect(settings.DB_PATH) as c:
        cur = await c.execute("SELECT scanned_at FROM gifts WHERE slug=?", (slug,))
        r = await cur.fetchone()
    return bool(r and time.time() - r[0] < settings.CACHE_TTL)


async def _rows(sql, params=()):
    async with aiosqlite.connect(settings.DB_PATH) as c:
        c.row_factory = aiosqlite.Row
        cur = await c.execute(sql, params)
        return [dict(r) for r in await cur.fetchall()]


async def gifts(f, limit=30, offset=0):
    w, p = _where(f)
    return await _rows(f"SELECT * FROM gifts{w} ORDER BY collection, num LIMIT ? OFFSET ?", p + [limit, offset])


async def stats(f):
    w, p = _where(f)
    r = await _rows(
        f"SELECT COUNT(*) total, COUNT(DISTINCT lower(owner_username)) owners, "
        f"SUM(owner_username IS NULL) no_username FROM gifts{w}", p)
    d = r[0]; d["no_username"] = d["no_username"] or 0
    return d


async def facet(kind, limit=200):
    if kind not in FACETS:
        return []
    return await _rows(
        f"SELECT {kind} name, COUNT(*) count FROM gifts WHERE {kind} IS NOT NULL "
        f"GROUP BY {kind} ORDER BY count DESC LIMIT ?", [limit])


async def owners(limit=50, offset=0):
    return await _rows(
        "SELECT owner_username username, COUNT(*) count FROM gifts WHERE owner_username IS NOT NULL "
        "GROUP BY lower(owner_username) ORDER BY count DESC LIMIT ? OFFSET ?", [limit, offset])


async def fav_list(uid):
    return await _rows("SELECT g.* FROM favorites f JOIN gifts g ON g.slug=f.slug WHERE f.user_id=?", [uid])


async def fav_set(uid, slug, on):
    async with aiosqlite.connect(settings.DB_PATH) as c:
        if on:
            await c.execute("INSERT OR IGNORE INTO favorites VALUES(?,?)", (uid, slug))
        else:
            await c.execute("DELETE FROM favorites WHERE user_id=? AND slug=?", (uid, slug))
        await c.commit()


async def hist_add(uid, query):
    async with aiosqlite.connect(settings.DB_PATH) as c:
        await c.execute("INSERT INTO history(user_id,query,created_at) VALUES(?,?,?)", (uid, query, int(time.time())))
        await c.commit()


async def hist_list(uid, limit=30):
    return await _rows("SELECT query, created_at FROM history WHERE user_id=? ORDER BY id DESC LIMIT ?", [uid, limit])
