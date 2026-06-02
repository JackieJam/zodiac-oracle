from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import app
from xingzuo.astro_engine import get_period_range, normalize_sign, sign_from_birth_date
from xingzuo.content_writer import ContentWriter
from xingzuo.secrets import DEEPSEEK_KEYCHAIN_SERVICE


client = TestClient(app)


def test_sign_alias_and_birth_date_mapping():
    assert normalize_sign("白羊座") == "aries"
    assert sign_from_birth_date(date(1990, 3, 21)) == "aries"
    assert sign_from_birth_date(date(1990, 12, 31)) == "capricorn"
    with pytest.raises(ValueError):
        normalize_sign("not-a-sign")


def test_weekly_period_starts_on_monday():
    period = get_period_range(date(2026, 5, 28), "weekly")
    assert period.start == date(2026, 5, 25)
    assert period.end == date(2026, 5, 31)


def test_public_api_returns_traceable_evidence():
    response = client.get("/api/horoscope/public?sign=aries&period=daily&date=2026-05-28")
    assert response.status_code == 200
    data = response.json()
    assert data["sign"] == "aries"
    assert data["scores"]["career"]["label"] == "事业"
    assert data["deep_reading"]["headline"]
    assert data["suggested_questions"]
    assert data["evidence"]
    assert {"planet", "aspect", "orb", "theme", "confidence"} <= set(data["evidence"][0])


def test_personal_api_accepts_missing_birth_time():
    response = client.post(
        "/api/horoscope/personal",
        json={
            "birth_date": "1990-03-21",
            "timezone": "Asia/Shanghai",
            "latitude": 31.23,
            "longitude": 121.474,
            "period": "weekly",
            "date": "2026-05-28",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "personal"
    assert data["birth_summary"]
    assert data["period"]["type"] == "weekly"


def test_personal_api_rejects_invalid_coordinates():
    response = client.post(
        "/api/horoscope/personal",
        json={
            "birth_date": "1990-03-21",
            "timezone": "Asia/Shanghai",
            "latitude": 120,
            "longitude": 121.474,
        },
    )
    assert response.status_code == 422


def test_content_writer_falls_back_without_llm(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("xingzuo.secrets._read_macos_keychain", lambda service: None)
    writer = ContentWriter()
    assert writer._try_llm_polish({"summary": "x"}) is None


def test_ask_api_uses_rule_fallback_without_llm(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("xingzuo.secrets._read_macos_keychain", lambda service: None)
    report = client.get("/api/horoscope/public?sign=aries&period=daily&date=2026-05-28").json()
    response = client.post(
        "/api/horoscope/ask",
        json={"report": report, "question": "今天感情上最该避开什么？"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "rules"
    assert data["answer"]
    assert data["grounding"]


def test_deepseek_config_takes_priority(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test")
    monkeypatch.delenv("DEEPSEEK_CHAT_COMPLETIONS_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    config = ContentWriter._llm_config()
    assert config["api_key"] == "deepseek-test"
    assert config["endpoint"] == "https://api.deepseek.com/chat/completions"
    assert config["model"] == "deepseek-v4-flash"


def test_deepseek_key_can_come_from_keychain(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY_FILE", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.setattr(
        "xingzuo.secrets._read_macos_keychain",
        lambda service: "keychain-test" if service == DEEPSEEK_KEYCHAIN_SERVICE else None,
    )
    config = ContentWriter._llm_config()
    assert config["api_key"] == "keychain-test"
    assert config["model"] == "deepseek-v4-flash"


def test_deepseek_key_can_come_from_file(monkeypatch, tmp_path):
    key_file = tmp_path / "deepseek.key"
    key_file.write_text("file-test\n")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY_FILE", str(key_file))
    monkeypatch.setattr("xingzuo.secrets._read_macos_keychain", lambda service: None)
    config = ContentWriter._llm_config()
    assert config["api_key"] == "file-test"
    assert config["model"] == "deepseek-v4-flash"
