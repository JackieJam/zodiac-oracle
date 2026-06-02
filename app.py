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

from datetime import date, datetime, time
import os
import sqlite3
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from xingzuo.astro_engine import AstroEngine, get_period_range, normalize_sign
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


def get_real_ip(request: Request) -> str:
    """获取真实IP地址，支持反向代理"""
    if not request:
        return ""
    # 优先从X-Forwarded-For获取（Caddy反向代理会设置）
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # 取第一个IP（客户端真实IP）
        return forwarded_for.split(",")[0].strip()
    # 其次从X-Real-IP获取
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    # 最后从request.client获取
    if request.client:
        return request.client.host
    return ""


# ====== 数据库 ======

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    # 查询日志
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
    # 追问日志
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


def log_query(sign: str, period: str, query_type: str,
              name: str = "", birth_date: str = "",
              client_ip: str = "", user_agent: str = ""):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO query_logs (sign, period, query_type, name, birth_date, client_ip, user_agent) "
        "VALUES (?,?,?,?,?,?,?)",
        (sign, period, query_type, name, birth_date, client_ip, user_agent or "")
    )
    conn.commit()
    conn.close()


def log_ask(sign: str, question: str, client_ip: str = "", user_agent: str = ""):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO ask_logs (sign, question, client_ip, user_agent) VALUES (?,?,?,?)",
        (sign, question, client_ip, user_agent or "")
    )
    conn.commit()
    conn.close()


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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "generated_at": datetime.now().isoformat()}


@app.get("/api/horoscope/public")
def public_horoscope(sign: str, period: Period = "daily", date_: date | None = Query(default=None, alias="date"),
                     request: Request = None):
    target_date = date_ or date.today()
    try:
        normalized_sign = normalize_sign(sign)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    period_range = get_period_range(target_date, period)
    context = astro_engine.public_context(normalized_sign, period_range)
    forecast = rule_engine.score(context)
    # 记录查询
    client_ip = get_real_ip(request)
    user_agent = request.headers.get("user-agent", "") if request else ""
    log_query(normalized_sign, period, "public", client_ip=client_ip, user_agent=user_agent)
    return content_writer.write(forecast)


@app.post("/api/horoscope/personal")
def personal_horoscope(payload: PersonalRequest, request: Request = None):
    period_range = get_period_range(payload.target_date, payload.period)
    try:
        context = astro_engine.personal_context(
            birth_date=payload.birth_date,
            birth_time=payload.birth_time,
            timezone=payload.timezone,
            latitude=payload.latitude,
            longitude=payload.longitude,
            period_range=period_range,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    forecast = rule_engine.score(context)
    # 记录查询
    client_ip = get_real_ip(request)
    user_agent = request.headers.get("user-agent", "") if request else ""
    log_query("personal", payload.period, "personal",
              name=payload.name or "", birth_date=str(payload.birth_date),
              client_ip=client_ip, user_agent=user_agent)
    return content_writer.write(forecast)


@app.post("/api/horoscope/ask")
def ask_horoscope(payload: AskRequest, request: Request = None):
    # 记录追问
    client_ip = get_real_ip(request)
    user_agent = request.headers.get("user-agent", "") if request else ""
    sign = payload.report.get("sign", "") if isinstance(payload.report, dict) else ""
    log_ask(sign, payload.question, client_ip=client_ip, user_agent=user_agent)
    return content_writer.answer_question(payload.report, payload.question)


# ====== 统计接口 ======

@app.get("/api/logs")
def get_query_logs(limit: int = 50, offset: int = 0):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) FROM query_logs").fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM query_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    conn.close()
    return {"total": total, "limit": limit, "offset": offset, "records": [dict(r) for r in rows]}


@app.get("/api/logs/stats")
def get_log_stats():
    conn = sqlite3.connect(str(DB_PATH))
    # 今日/总计查询
    today_queries = conn.execute(
        "SELECT COUNT(*) FROM query_logs WHERE date(created_at) = date('now', 'localtime')"
    ).fetchone()[0]
    total_queries = conn.execute("SELECT COUNT(*) FROM query_logs").fetchone()[0]
    # 今日/总计追问
    today_asks = conn.execute(
        "SELECT COUNT(*) FROM ask_logs WHERE date(created_at) = date('now', 'localtime')"
    ).fetchone()[0]
    total_asks = conn.execute("SELECT COUNT(*) FROM ask_logs").fetchone()[0]
    # 热门星座排行
    top_signs = conn.execute(
        "SELECT sign, COUNT(*) as cnt FROM query_logs WHERE sign != 'personal' "
        "GROUP BY sign ORDER BY cnt DESC LIMIT 12"
    ).fetchall()
    # 公共/个人化比例
    public_count = conn.execute(
        "SELECT COUNT(*) FROM query_logs WHERE query_type = 'public'"
    ).fetchone()[0]
    personal_count = conn.execute(
        "SELECT COUNT(*) FROM query_logs WHERE query_type = 'personal'"
    ).fetchone()[0]
    # 今日/本周比例
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
        "weekly_count": weekly_count
    }


@app.get("/api/ask/logs")
def get_ask_logs(limit: int = 50, offset: int = 0):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) FROM ask_logs").fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM ask_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    conn.close()
    return {"total": total, "limit": limit, "offset": offset, "records": [dict(r) for r in rows]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8512, reload=False)
