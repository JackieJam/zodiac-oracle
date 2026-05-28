from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal

import swisseph as swe


Period = Literal["daily", "weekly"]

SIGN_ORDER = [
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
]

SIGN_NAMES = {
    "aries": "白羊座",
    "taurus": "金牛座",
    "gemini": "双子座",
    "cancer": "巨蟹座",
    "leo": "狮子座",
    "virgo": "处女座",
    "libra": "天秤座",
    "scorpio": "天蝎座",
    "sagittarius": "射手座",
    "capricorn": "摩羯座",
    "aquarius": "水瓶座",
    "pisces": "双鱼座",
}

SIGN_ALIASES = {
    **{sign: sign for sign in SIGN_ORDER},
    "白羊": "aries",
    "白羊座": "aries",
    "金牛": "taurus",
    "金牛座": "taurus",
    "双子": "gemini",
    "双子座": "gemini",
    "巨蟹": "cancer",
    "巨蟹座": "cancer",
    "狮子": "leo",
    "狮子座": "leo",
    "处女": "virgo",
    "处女座": "virgo",
    "天秤": "libra",
    "天秤座": "libra",
    "天蝎": "scorpio",
    "天蝎座": "scorpio",
    "射手": "sagittarius",
    "射手座": "sagittarius",
    "摩羯": "capricorn",
    "摩羯座": "capricorn",
    "水瓶": "aquarius",
    "水瓶座": "aquarius",
    "双鱼": "pisces",
    "双鱼座": "pisces",
}

SIGN_DATE_RANGES = [
    ((3, 21), "aries"),
    ((4, 20), "taurus"),
    ((5, 21), "gemini"),
    ((6, 22), "cancer"),
    ((7, 23), "leo"),
    ((8, 23), "virgo"),
    ((9, 23), "libra"),
    ((10, 24), "scorpio"),
    ((11, 22), "sagittarius"),
    ((12, 22), "capricorn"),
    ((1, 20), "aquarius"),
    ((2, 19), "pisces"),
]

PLANETS = {
    "Sun": {"id": swe.SUN, "cn": "太阳"},
    "Moon": {"id": swe.MOON, "cn": "月亮"},
    "Mercury": {"id": swe.MERCURY, "cn": "水星"},
    "Venus": {"id": swe.VENUS, "cn": "金星"},
    "Mars": {"id": swe.MARS, "cn": "火星"},
    "Jupiter": {"id": swe.JUPITER, "cn": "木星"},
    "Saturn": {"id": swe.SATURN, "cn": "土星"},
    "Uranus": {"id": swe.URANUS, "cn": "天王星"},
    "Neptune": {"id": swe.NEPTUNE, "cn": "海王星"},
    "Pluto": {"id": swe.PLUTO, "cn": "冥王星"},
}

ASPECTS = [
    ("conjunction", 0, 8, "合相"),
    ("sextile", 60, 4, "六合"),
    ("square", 90, 6, "刑相"),
    ("trine", 120, 6, "拱相"),
    ("opposition", 180, 7, "冲相"),
]

SWISS_EPHEMERIS_NOTICE = "Swiss Ephemeris / pyswisseph；热带黄道，地心黄经。商业发布前需确认 AGPL 或商业授权。"


@dataclass(frozen=True)
class PeriodRange:
    period: Period
    start: date
    end: date


@dataclass(frozen=True)
class AstroFactor:
    planet: str
    aspect: str
    aspect_cn: str
    target: str
    orb: float
    theme: str
    polarity: Literal["supportive", "challenging", "mixed"]
    weight: float
    description: str


@dataclass(frozen=True)
class AstroContext:
    mode: Literal["public", "personal"]
    sign: str
    sign_name: str
    period: PeriodRange
    factors: list[AstroFactor]
    subject: str
    birth_summary: str | None = None


def normalize_sign(value: str) -> str:
    normalized = value.strip().lower()
    sign = SIGN_ALIASES.get(normalized) or SIGN_ALIASES.get(value.strip())
    if not sign:
        raise ValueError(f"Unsupported zodiac sign: {value}")
    return sign


def sign_from_birth_date(birth_date: date) -> str:
    month_day = (birth_date.month, birth_date.day)
    if month_day >= (12, 22) or month_day < (1, 20):
        return "capricorn"
    for boundary, sign in SIGN_DATE_RANGES:
        if month_day < boundary:
            previous_index = (SIGN_ORDER.index(sign) - 1) % len(SIGN_ORDER)
            return SIGN_ORDER[previous_index]
    return "pisces"


def sign_from_longitude(longitude: float) -> str:
    return SIGN_ORDER[int(_normalize_degrees(longitude) // 30)]


def get_period_range(target_date: date, period: Period) -> PeriodRange:
    if period == "daily":
        return PeriodRange(period=period, start=target_date, end=target_date)
    if period == "weekly":
        start = target_date - timedelta(days=target_date.weekday())
        return PeriodRange(period=period, start=start, end=start + timedelta(days=6))
    raise ValueError(f"Unsupported period: {period}")


class AstroEngine:
    """Swiss Ephemeris based tropical astrology engine."""

    def public_context(self, sign: str, period_range: PeriodRange) -> AstroContext:
        sign_point = SIGN_ORDER.index(sign) * 30 + 15
        factors = self._transit_to_point_factors(
            period_range=period_range,
            point_longitude=sign_point,
            target_label=f"{SIGN_NAMES[sign]}太阳点",
            limit=4 if period_range.period == "daily" else 7,
        )
        return AstroContext(
            mode="public",
            sign=sign,
            sign_name=SIGN_NAMES[sign],
            period=period_range,
            factors=factors,
            subject=f"{SIGN_NAMES[sign]}大众运势",
        )

    def personal_context(
        self,
        birth_date: date,
        birth_time: time | None,
        timezone: str,
        latitude: float,
        longitude: float,
        period_range: PeriodRange,
        name: str | None = None,
    ) -> AstroContext:
        local_zone = _zoneinfo(timezone)
        effective_birth_time = birth_time or time(12, 0)
        birth_dt = datetime.combine(birth_date, effective_birth_time, tzinfo=local_zone)
        birth_utc = birth_dt.astimezone(timezone_utc())
        natal_positions = self._planet_positions(_julian_day(birth_utc))
        sun_sign = sign_from_longitude(natal_positions["Sun"])
        factors = self._transit_to_natal_factors(
            period_range=period_range,
            natal_positions=natal_positions,
            limit=5 if period_range.period == "daily" else 8,
        )
        birth_time_text = birth_time.isoformat(timespec="minutes") if birth_time else "未提供出生时间，按当地 12:00 估算"
        birth_summary = (
            f"{birth_date.isoformat()} {birth_time_text}，{timezone}，"
            f"纬度 {latitude:.3f}，经度 {longitude:.3f}；本命太阳 {SIGN_NAMES[sun_sign]}。"
        )
        subject = f"{name}的个人运势" if name else f"{SIGN_NAMES[sun_sign]}个人运势"
        return AstroContext(
            mode="personal",
            sign=sun_sign,
            sign_name=SIGN_NAMES[sun_sign],
            period=period_range,
            factors=factors,
            subject=subject,
            birth_summary=birth_summary,
        )

    def _transit_to_point_factors(
        self,
        period_range: PeriodRange,
        point_longitude: float,
        target_label: str,
        limit: int,
    ) -> list[AstroFactor]:
        factors: list[AstroFactor] = []
        for sample_date in _sample_dates(period_range):
            transit_positions = self._planet_positions(_julian_day_for_date(sample_date))
            for planet, longitude in transit_positions.items():
                factor = self._aspect_factor(
                    transit_planet=planet,
                    transit_longitude=longitude,
                    target_label=target_label,
                    target_longitude=point_longitude,
                    target_planet=None,
                    sample_date=sample_date,
                )
                if factor:
                    factors.append(factor)
        return self._rank_and_dedupe(factors, limit)

    def _transit_to_natal_factors(
        self,
        period_range: PeriodRange,
        natal_positions: dict[str, float],
        limit: int,
    ) -> list[AstroFactor]:
        factors: list[AstroFactor] = []
        natal_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
        for sample_date in _sample_dates(period_range):
            transit_positions = self._planet_positions(_julian_day_for_date(sample_date))
            for transit_planet, transit_longitude in transit_positions.items():
                for natal_planet in natal_planets:
                    factor = self._aspect_factor(
                        transit_planet=transit_planet,
                        transit_longitude=transit_longitude,
                        target_label=f"本命{PLANETS[natal_planet]['cn']}",
                        target_longitude=natal_positions[natal_planet],
                        target_planet=natal_planet,
                        sample_date=sample_date,
                    )
                    if factor:
                        factors.append(factor)
        return self._rank_and_dedupe(factors, limit)

    def _planet_positions(self, julian_day: float) -> dict[str, float]:
        positions: dict[str, float] = {}
        for planet, meta in PLANETS.items():
            result, _flags = swe.calc_ut(julian_day, meta["id"])
            positions[planet] = _normalize_degrees(result[0])
        return positions

    def _aspect_factor(
        self,
        transit_planet: str,
        transit_longitude: float,
        target_label: str,
        target_longitude: float,
        target_planet: str | None,
        sample_date: date,
    ) -> AstroFactor | None:
        separation = _angular_distance(transit_longitude, target_longitude)
        candidates = []
        for aspect, angle, max_orb, aspect_cn in ASPECTS:
            orb = abs(separation - angle)
            if orb <= max_orb:
                candidates.append((orb, aspect, angle, max_orb, aspect_cn))
        if not candidates:
            return None

        orb, aspect, angle, max_orb, aspect_cn = min(candidates, key=lambda item: item[0])
        theme = self._theme_for(transit_planet, target_planet, aspect)
        polarity = self._polarity_for(aspect, transit_planet)
        weight = round(max(0.2, 1 - orb / max_orb), 2)
        transit_cn = PLANETS[transit_planet]["cn"]
        transit_sign = SIGN_NAMES[sign_from_longitude(transit_longitude)]
        return AstroFactor(
            planet=transit_planet,
            aspect=aspect,
            aspect_cn=aspect_cn,
            target=target_label,
            orb=round(orb, 2),
            theme=theme,
            polarity=polarity,
            weight=weight,
            description=(
                f"{sample_date.isoformat()} 行运{transit_cn}位于{transit_sign} "
                f"{transit_longitude:.2f}°，与{target_label}形成{angle}度{aspect_cn}，"
                f"容许度 {orb:.2f}°。"
            ),
        )

    @staticmethod
    def _rank_and_dedupe(factors: list[AstroFactor], limit: int) -> list[AstroFactor]:
        best: dict[tuple[str, str, str], AstroFactor] = {}
        for factor in factors:
            key = (factor.planet, factor.aspect, factor.target)
            if key not in best or factor.weight > best[key].weight:
                best[key] = factor
        ranked = sorted(best.values(), key=lambda item: (item.weight, -item.orb), reverse=True)
        return ranked[:limit]

    @staticmethod
    def _theme_for(transit_planet: str, target_planet: str | None, aspect: str) -> str:
        planet_themes = {
            "Sun": "自我表达",
            "Moon": "情绪节奏",
            "Mercury": "沟通判断",
            "Venus": "亲密关系",
            "Mars": "行动力",
            "Jupiter": "机会扩张",
            "Saturn": "责任边界",
            "Uranus": "变化突破",
            "Neptune": "直觉想象",
            "Pluto": "深层转化",
        }
        target_themes = {
            "Sun": "长期方向",
            "Moon": "安全感",
            "Mercury": "学习效率",
            "Venus": "合作氛围",
            "Mars": "竞争压力",
            "Jupiter": "贵人资源",
            "Saturn": "结构压力",
        }
        if aspect in {"square", "opposition"} and target_planet:
            return target_themes[target_planet]
        return planet_themes[transit_planet]

    @staticmethod
    def _polarity_for(aspect: str, planet: str) -> Literal["supportive", "challenging", "mixed"]:
        if aspect in {"trine", "sextile"}:
            return "supportive"
        if aspect in {"square", "opposition"}:
            return "challenging"
        return "mixed" if planet in {"Saturn", "Uranus", "Neptune", "Pluto", "Mars"} else "supportive"


def _zoneinfo(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unsupported timezone: {timezone_name}") from exc


def timezone_utc() -> timezone:
    return timezone.utc


def _julian_day(moment_utc: datetime) -> float:
    utc = moment_utc.astimezone(timezone.utc)
    hour = utc.hour + utc.minute / 60 + utc.second / 3600
    return swe.julday(utc.year, utc.month, utc.day, hour)


def _julian_day_for_date(sample_date: date) -> float:
    return swe.julday(sample_date.year, sample_date.month, sample_date.day, 12.0)


def _sample_dates(period_range: PeriodRange) -> list[date]:
    days = (period_range.end - period_range.start).days + 1
    return [period_range.start + timedelta(days=offset) for offset in range(days)]


def _normalize_degrees(value: float) -> float:
    return value % 360


def _angular_distance(first: float, second: float) -> float:
    distance = abs(_normalize_degrees(first) - _normalize_degrees(second))
    return min(distance, 360 - distance)
