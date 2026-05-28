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
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from xingzuo.astro_engine import AstroEngine, get_period_range, normalize_sign
from xingzuo.content_writer import ContentWriter
from xingzuo.forecast_rules import ForecastRuleEngine


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

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
def public_horoscope(sign: str, period: Period = "daily", date_: date | None = Query(default=None, alias="date")):
    target_date = date_ or date.today()
    try:
        normalized_sign = normalize_sign(sign)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    period_range = get_period_range(target_date, period)
    context = astro_engine.public_context(normalized_sign, period_range)
    forecast = rule_engine.score(context)
    return content_writer.write(forecast)


@app.post("/api/horoscope/personal")
def personal_horoscope(payload: PersonalRequest):
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
    return content_writer.write(forecast)


@app.post("/api/horoscope/ask")
def ask_horoscope(payload: AskRequest):
    return content_writer.answer_question(payload.report, payload.question)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
