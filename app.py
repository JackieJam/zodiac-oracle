# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastapi>=0.115.0",
#   "pyswisseph>=2.10.3.2",
#   "uvicorn>=0.30.0",
#   "pydantic>=2.8.0",
# ]
# ///

from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import date, datetime, time, timedelta
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from xingzuo.astro_engine import AstroEngine, get_period_range, normalize_sign, SIGN_ORDER
from xingzuo.content_writer import ContentWriter
from xingzuo.forecast_rules import ForecastRuleEngine


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "horoscope_logs.db"

# 使用与 bazi 相同的 DeepSeek 配置
os.environ.setdefault("DEEPSEEK_MODEL", "deepseek-chat")
os.environ.setdefault("DEEPSEEK_CHAT_COMPLETIONS_URL", "https://api.deepseek.com/chat/completions")

app = FastAPI(
    title="Xingzuo Professional Horoscope",
    description="Western tropical astrology daily and weekly forecast prototype.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

astro_engine = AstroEngine()
rule_engine = ForecastRuleEngine()
content_writer = ContentWriter()

Period = Literal["daily", "weekly"]

# CPU 密集型任务线程池（Swiss Ephemeris 计算）
_executor = None


def _get_executor():
    global _executor
    if _executor is None:
        from concurrent.futures import ThreadPoolExecutor
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="astro")
    return _executor


def get_real_ip(request: Request) -> str:
    """获取真实IP地址，支持反向代理"""
    if not request:
        return ""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return ""


# ====================================================================
# 优化 3: SQLite 异步写入队列
# ====================================================================

_log_queue: asyncio.Queue | None = None
_log_thread: threading.Thread | None = None
_log_loop: asyncio.AbstractEventLoop | None = None


class _LogWriter:
    """后台单线程消费日志写入队列，避免并发写 SQLite 锁冲突。"""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None

    def start(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._task = loop.create_task(self._run())

    async def _run(self):
        while True:
            try:
                sql, params = await self._queue.get()
                await asyncio.get_event_loop().run_in_executor(
                    None, self._write_sync, sql, params
                )
            except Exception:
                pass  # 日志写入失败不影响主流程

    @staticmethod
    def _write_sync(sql: str, params: tuple):
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=5)
            conn.execute(sql, params)
            conn.commit()
            conn.close()
        except Exception:
            pass

    async def enqueue(self, sql: str, params: tuple):
        if self._loop and not self._queue.full():
            await self._queue.put((sql, params))


_log_writer = _LogWriter()


# ====================================================================
# 数据库初始化
# ====================================================================

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_logs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            sign          TEXT NOT NULL,
            period        TEXT NOT NULL DEFAULT 'daily',
            query_type    TEXT NOT NULL DEFAULT 'public',
            name          TEXT DEFAULT '',
            birth_date    TEXT DEFAULT '',
            client_ip     TEXT DEFAULT '',
            user_agent    TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ask_logs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            sign          TEXT DEFAULT '',
            question      TEXT NOT NULL,
            client_ip     TEXT DEFAULT '',
            user_agent    TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

init_db()


def _log_query_async(sign: str, period: str, query_type: str,
                     name: str = "", birth_date: str = "",
                     client_ip: str = "", user_agent: str = ""):
    """异步写入查询日志（不阻塞请求）。"""
    sql = ("INSERT INTO query_logs (sign, period, query_type, name, birth_date, client_ip, user_agent) "
           "VALUES (?,?,?,?,?,?,?)")
    params = (sign, period, query_type, name, birth_date, client_ip, user_agent or "")
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_log_writer.enqueue(sql, params))
    except RuntimeError:
        # 没有事件循环时同步写
        _LogWriter._write_sync(sql, params)


def _log_ask_async(sign: str, question: str, client_ip: str = "", user_agent: str = ""):
    """异步写入追问日志。"""
    sql = "INSERT INTO ask_logs (sign, question, client_ip, user_agent) VALUES (?,?,?,?)"
    params = (sign, question, client_ip, user_agent or "")
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_log_writer.enqueue(sql, params))
    except RuntimeError:
        _LogWriter._write_sync(sql, params)


# ====================================================================
# 优化 2: 排名缓存 — 每天每种 period 只算一次 12 星座分数
# ====================================================================

class _RankingCache:
    """缓存 12 星座分数，按 (period, date) 键控，每天自动过期。"""

    def __init__(self, ttl_hours: int = 12):
        self._cache: OrderedDict[tuple[str, str], dict[str, int]] = OrderedDict()
        self._ranking: OrderedDict[tuple[str, str], dict] = OrderedDict()
        self._generated: OrderedDict[tuple[str, str], datetime] = OrderedDict()
        self._ttl = timedelta(hours=ttl_hours)
        self._lock = threading.Lock()

    def get_scores(self, period: str, date_iso: str) -> dict[str, int] | None:
        key = (period, date_iso)
        with self._lock:
            if key in self._cache:
                if datetime.now() - self._generated[key] < self._ttl:
                    return self._cache[key]
                # 过期清理
                del self._cache[key]
                del self._ranking[key]
                del self._generated[key]
        return None

    def get_ranking(self, period: str, date_iso: str, sign: str) -> dict | None:
        key = (period, date_iso)
        with self._lock:
            if key in self._ranking:
                if datetime.now() - self._generated[key] < self._ttl:
                    scores = self._cache[key]
                    return rule_engine.compute_ranking(scores, sign)
        return None

    def put(self, period: str, date_iso: str, scores: dict[str, int]):
        key = (period, date_iso)
        with self._lock:
            self._cache[key] = scores
            self._ranking[key] = True  # 标记已缓存
            self._generated[key] = datetime.now()
            # 淘汰旧条目（保留最近 10 个）
            while len(self._cache) > 10:
                self._cache.popitem(last=False)
                self._ranking.popitem(last=False)
                self._generated.popitem(last=False)


_ranking_cache = _RankingCache(ttl_hours=12)


# ====================================================================
# 优化 4: 接口级缓存 — public 报告按 sign+period+date 带 TTL
# ====================================================================

class _ReportCache:
    """带 TTL 的报告缓存，避免 lru_cache 无过期的问题。"""

    def __init__(self, ttl_hours: int = 6):
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._generated: OrderedDict[str, datetime] = OrderedDict()
        self._ttl = timedelta(hours=ttl_hours)
        self._lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        with self._lock:
            if key in self._cache:
                if datetime.now() - self._generated[key] < self._ttl:
                    return self._cache[key]
                del self._cache[key]
                del self._generated[key]
        return None

    def put(self, key: str, value: dict):
        with self._lock:
            self._cache[key] = value
            self._generated[key] = datetime.now()
            while len(self._cache) > 512:
                self._cache.popitem(last=False)
                self._generated.popitem(last=False)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._generated.clear()


_report_cache = _ReportCache(ttl_hours=6)


async def build_public_report(sign: str, period: Period, target_date_iso: str) -> dict[str, Any]:
    """构建 public 报告（带缓存 + 排名缓存）。"""
    cache_key = f"{sign}:{period}:{target_date_iso}"

    # 1. 检查报告缓存
    cached = _report_cache.get(cache_key)
    if cached:
        return cached

    target_date = date.fromisoformat(target_date_iso)
    period_range = get_period_range(target_date, period)

    # 2. CPU 密集计算放线程池
    loop = asyncio.get_running_loop()
    executor = _get_executor()

    # 2a. 计算星座运势
    context = await loop.run_in_executor(
        executor, astro_engine.public_context, sign, period_range
    )
    forecast = await loop.run_in_executor(
        executor, rule_engine.score, context
    )

    # 2b. 排名计算 — 优先从缓存取
    all_scores = _ranking_cache.get_scores(period, target_date_iso)
    if all_scores is None:
        # 缓存未命中，计算全部 12 星座
        all_scores = await loop.run_in_executor(
            executor, rule_engine.score_all_signs, period_range, astro_engine
        )
        _ranking_cache.put(period, target_date_iso, all_scores)

    ranking = rule_engine.compute_ranking(all_scores, sign)

    # 3. 生成报告内容（轻量，直接执行）
    result = content_writer.write_fast(forecast, ranking)

    # 4. 存入报告缓存
    _report_cache.put(cache_key, result)

    return result


# ====================================================================
# 模型定义
# ====================================================================

class PersonalRequest(BaseModel):
    birth_date: date
    birth_time: time | None = None
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    period: Period = "daily"
    target_date: date = Field(default_factory=date.today, alias="date")
    name: str | None = Field(default=None, max_length=48)

    @field_validator("timezone")
    @classmethod
    def reject_blank_timezone(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("timezone cannot be blank")
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unsupported timezone: {normalized}") from exc
        return normalized


class AskRequest(BaseModel):
    report: dict[str, Any]
    question: str = Field(default="今天我最应该注意什么？", max_length=240)


# ====================================================================
# 路由 — 全部 async
# ====================================================================

@app.on_event("startup")
async def startup():
    _log_writer.start(asyncio.get_running_loop())


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "generated_at": datetime.now().isoformat()}


@app.get("/api/horoscope/public")
async def public_horoscope(
    sign: str,
    period: Period = "daily",
    date_: date | None = Query(default=None, alias="date"),
    request: Request = None,
):
    target_date = date_ or date.today()
    try:
        normalized_sign = normalize_sign(sign)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 异步写日志（不阻塞响应）
    client_ip = get_real_ip(request)
    user_agent = request.headers.get("user-agent", "") if request else ""
    _log_query_async(normalized_sign, period, "public", client_ip=client_ip, user_agent=user_agent)

    return await build_public_report(normalized_sign, period, target_date.isoformat())


@app.post("/api/horoscope/personal")
async def personal_horoscope(payload: PersonalRequest, request: Request = None):
    period_range = get_period_range(payload.target_date, payload.period)

    # CPU 密集计算放线程池
    loop = asyncio.get_running_loop()
    executor = _get_executor()

    try:
        context = await loop.run_in_executor(
            executor,
            lambda: astro_engine.personal_context(
                birth_date=payload.birth_date,
                birth_time=payload.birth_time,
                timezone=payload.timezone,
                latitude=payload.latitude,
                longitude=payload.longitude,
                period_range=period_range,
                name=payload.name,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    forecast = await loop.run_in_executor(executor, rule_engine.score, context)

    # 异步写日志
    client_ip = get_real_ip(request)
    user_agent = request.headers.get("user-agent", "") if request else ""
    _log_query_async("personal", payload.period, "personal",
                     name=payload.name or "", birth_date=str(payload.birth_date),
                     client_ip=client_ip, user_agent=user_agent)

    return content_writer.write(forecast)


@app.post("/api/horoscope/ask")
async def ask_horoscope(payload: AskRequest, request: Request = None):
    # 异步写日志
    client_ip = get_real_ip(request)
    user_agent = request.headers.get("user-agent", "") if request else ""
    sign = payload.report.get("sign", "") if isinstance(payload.report, dict) else ""
    _log_ask_async(sign, payload.question, client_ip=client_ip, user_agent=user_agent)

    # LLM 调用本身是阻塞的，放线程池
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _get_executor(), content_writer.answer_question, payload.report, payload.question
    )


# ====================================================================
# 统计接口（读操作，直接 async + 线程池）
# ====================================================================

def _query_db(sql: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False):
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(sql, params)
    if fetchone:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()
    else:
        result = None
    conn.close()
    return result


@app.get("/api/logs")
async def get_query_logs(limit: int = 50, offset: int = 0):
    loop = asyncio.get_running_loop()
    executor = _get_executor()
    total = await loop.run_in_executor(
        executor, _query_db, "SELECT COUNT(*) FROM query_logs", (), True, False
    )
    rows = await loop.run_in_executor(
        executor, _query_db,
        "SELECT * FROM query_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
        False, True
    )
    return {
        "total": total[0] if total else 0,
        "limit": limit,
        "offset": offset,
        "records": [dict(r) for r in (rows or [])],
    }


@app.get("/api/logs/stats")
async def get_log_stats():
    loop = asyncio.get_running_loop()
    executor = _get_executor()

    def _stats():
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        today_queries = conn.execute(
            "SELECT COUNT(*) FROM query_logs WHERE date(created_at) = date('now', 'localtime')"
        ).fetchone()[0]
        total_queries = conn.execute("SELECT COUNT(*) FROM query_logs").fetchone()[0]
        today_asks = conn.execute(
            "SELECT COUNT(*) FROM ask_logs WHERE date(created_at) = date('now', 'localtime')"
        ).fetchone()[0]
        total_asks = conn.execute("SELECT COUNT(*) FROM ask_logs").fetchone()[0]
        top_signs = conn.execute(
            "SELECT sign, COUNT(*) as cnt FROM query_logs WHERE sign != 'personal' "
            "GROUP BY sign ORDER BY cnt DESC LIMIT 12"
        ).fetchall()
        public_count = conn.execute(
            "SELECT COUNT(*) FROM query_logs WHERE query_type = 'public'"
        ).fetchone()[0]
        personal_count = conn.execute(
            "SELECT COUNT(*) FROM query_logs WHERE query_type = 'personal'"
        ).fetchone()[0]
        daily_count = conn.execute(
            "SELECT COUNT(*) FROM query_logs WHERE period = 'daily'"
        ).fetchone()[0]
        weekly_count = conn.execute(
            "SELECT COUNT(*) FROM query_logs WHERE period = 'weekly'"
        ).fetchone()[0]
        conn.close()
        return {
            "today_queries": today_queries,
            "total_queries": total_queries,
            "today_asks": today_asks,
            "total_asks": total_asks,
            "top_signs": [{"sign": r[0], "count": r[1]} for r in top_signs],
            "public_count": public_count,
            "personal_count": personal_count,
            "daily_count": daily_count,
            "weekly_count": weekly_count,
        }

    return await loop.run_in_executor(executor, _stats)


@app.get("/api/ask/logs")
async def get_ask_logs(limit: int = 50, offset: int = 0):
    loop = asyncio.get_running_loop()
    executor = _get_executor()
    total = await loop.run_in_executor(
        executor, _query_db, "SELECT COUNT(*) FROM ask_logs", (), True, False
    )
    rows = await loop.run_in_executor(
        executor, _query_db,
        "SELECT * FROM ask_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
        False, True
    )
    return {
        "total": total[0] if total else 0,
        "limit": limit,
        "offset": offset,
        "records": [dict(r) for r in (rows or [])],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8512, reload=False)
