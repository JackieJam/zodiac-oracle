from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from xingzuo.forecast_rules import AREA_NAMES, Forecast
from xingzuo.secrets import get_secret


DISCLAIMER = "本报告基于西洋热带占星的真实星历与规则解释模型生成，仅供自我观察与娱乐参考，不构成医疗、投资或法律建议。"
EPHEMERIS_NOTICE = "星历计算使用 Swiss Ephemeris / pyswisseph：热带黄道、地心黄经。商业发布前需确认 AGPL 或商业授权。"
DEFAULT_DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


class ContentWriter:
    def write(self, forecast: Forecast) -> dict[str, Any]:
        structured = self._structured_response(forecast)
        polished = self._try_llm_polish(structured)
        if polished:
            structured["summary"] = polished
            structured["writer"] = "rules+llm"
        return structured

    def _structured_response(self, forecast: Forecast) -> dict[str, Any]:
        context = forecast.context
        period_label = "今日" if context.period.period == "daily" else "本周"
        area_scores = {
            key: {"label": AREA_NAMES[key], "score": value}
            for key, value in forecast.scores.items()
        }
        if forecast.evidence:
            lead_theme = forecast.evidence[0]["theme"]
            summary = (
                f"{context.subject}{period_label}整体分为 {forecast.overall_score}。"
                f"真实行运重点落在{lead_theme}，建议先看清节奏，再决定投入强度。"
            )
        else:
            summary = (
                f"{context.subject}{period_label}整体分为 {forecast.overall_score}。"
                "主相位信号较少，适合维持稳定节奏，避免为了变化而变化。"
            )
        return {
            "subject": context.subject,
            "mode": context.mode,
            "sign": context.sign,
            "sign_name": context.sign_name,
            "period": {
                "type": context.period.period,
                "start": context.period.start.isoformat(),
                "end": context.period.end.isoformat(),
            },
            "birth_summary": context.birth_summary,
            "overall_score": forecast.overall_score,
            "scores": area_scores,
            "summary": summary,
            "deep_reading": self._deep_reading(forecast),
            "suggested_questions": self._suggested_questions(forecast),
            "highlights": forecast.highlights,
            "actions": forecast.actions,
            "evidence": forecast.evidence,
            "disclaimer": DISCLAIMER,
            "ephemeris_notice": EPHEMERIS_NOTICE,
            "generated_at": forecast.generated_at.isoformat(),
            "writer": "rules",
        }

    def answer_question(self, report: dict[str, Any], question: str) -> dict[str, Any]:
        normalized_question = question.strip()
        if not normalized_question:
            normalized_question = "今天我最应该注意什么？"

        llm_answer = self._try_llm_answer(report, normalized_question)
        if llm_answer:
            return {
                "answer": llm_answer,
                "source": "rules+llm",
                "grounding": self._grounding(report),
            }

        return {
            "answer": self._fallback_answer(report, normalized_question),
            "source": "rules",
            "grounding": self._grounding(report),
        }

    def _deep_reading(self, forecast: Forecast) -> dict[str, Any]:
        evidence = forecast.evidence
        lead = evidence[0] if evidence else None
        second = evidence[1] if len(evidence) > 1 else None
        weak_area = min(forecast.scores, key=forecast.scores.get)
        strong_area = max(forecast.scores, key=forecast.scores.get)
        weak_label = AREA_NAMES[weak_area]
        strong_label = AREA_NAMES[strong_area]
        if lead:
            headline = f"{lead['theme']}是这段时间的入口。"
            why = f"{lead['description']} 这说明事件不会只停留在表面感受，而是会推着你处理{lead['theme']}。"
            blind_spot = (
                f"{second['theme']}可能成为盲区，尤其当你急着证明自己时。"
                if second
                else f"{weak_label}能量较弱，适合慢一点确认事实。"
            )
            ritual = f"用 10 分钟写下一个和{lead['theme']}有关的具体决定，只保留今天能完成的一步。"
        else:
            headline = "主相位信号较少，稳定本身就是主题。"
            why = "行运没有形成强触发，适合维护秩序、复盘和轻量推进。"
            blind_spot = f"{weak_label}仍然需要留意，不要因为平静就忽略细节。"
            ritual = "做一次 15 分钟的清单整理，把今天必须完成和可以延后的事情分开。"

        return {
            "headline": headline,
            "why_it_matters": why,
            "blind_spot": blind_spot,
            "best_move": f"优先处理{strong_label}相关事项，把{weak_label}上的承诺降到可控范围。",
            "micro_ritual": ritual,
            "reflection_questions": self._suggested_questions(forecast)[:3],
        }

    def _suggested_questions(self, forecast: Forecast) -> list[str]:
        evidence = forecast.evidence
        top_theme = evidence[0]["theme"] if evidence else "今天的节奏"
        weak_area = AREA_NAMES[min(forecast.scores, key=forecast.scores.get)]
        return [
            f"{top_theme}具体会影响我什么？",
            f"今天在{weak_area}上要避开什么？",
            "我适合主动推进，还是先观察？",
            "如果只做一件事，应该做什么？",
        ]

    def _try_llm_polish(self, structured: dict[str, Any]) -> str | None:
        if not self._llm_config()["api_key"]:
            return None

        return self._call_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "你是专业、克制的西洋占星报告编辑。只能润色输入中的结构化结论，"
                        "不得新增不存在的行星、相位、宫位或确定性承诺。输出 120 字以内中文。"
                    ),
                },
                {"role": "user", "content": json.dumps(structured, ensure_ascii=False)},
            ],
            temperature=0.55,
        )

    def _try_llm_answer(self, report: dict[str, Any], question: str) -> str | None:
        if not self._llm_config()["api_key"]:
            return None

        compact_report = {
            "subject": report.get("subject"),
            "period": report.get("period"),
            "scores": report.get("scores"),
            "summary": report.get("summary"),
            "deep_reading": report.get("deep_reading"),
            "actions": report.get("actions"),
            "evidence": report.get("evidence", [])[:8],
        }
        return self._call_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "你是一个专业但不夸张的西洋占星顾问。必须只基于用户给出的真实星历报告回答，"
                        "不得新增未提供的行星、相位、宫位、事件预言或绝对承诺。"
                        "回答要有洞察、具体行动建议和温和边界，180 字以内中文。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"report": compact_report, "question": question},
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.7,
        )

    def _call_llm(self, messages: list[dict[str, str]], temperature: float) -> str | None:
        config = self._llm_config()
        api_key = config["api_key"]
        if not api_key:
            return None
        payload = {
            "model": config["model"],
            "temperature": temperature,
            "messages": messages,
        }
        request = urllib.request.Request(
            config["endpoint"],
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return None

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            return None

    @staticmethod
    def _llm_config() -> dict[str, str | None]:
        deepseek_key = get_secret("DEEPSEEK_API_KEY")
        if deepseek_key:
            return {
                "api_key": deepseek_key,
                "endpoint": os.getenv("DEEPSEEK_CHAT_COMPLETIONS_URL", DEFAULT_DEEPSEEK_ENDPOINT),
                "model": os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
            }

        openai_key = get_secret("OPENAI_API_KEY")
        return {
            "api_key": openai_key,
            "endpoint": os.getenv("OPENAI_CHAT_COMPLETIONS_URL", DEFAULT_OPENAI_ENDPOINT),
            "model": os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        }

    @staticmethod
    def _fallback_answer(report: dict[str, Any], question: str) -> str:
        evidence = report.get("evidence") or []
        scores = report.get("scores") or {}
        lead = evidence[0] if evidence else {}
        weak_key = None
        if scores:
            weak_key = min(scores, key=lambda key: scores[key].get("score", 100))
        weak_label = scores.get(weak_key, {}).get("label", "节奏") if weak_key else "节奏"
        lead_theme = lead.get("theme", "当前节奏")
        lead_description = lead.get("description", "当前主相位信号不强")

        if "感情" in question or "关系" in question:
            angle = "关系里先看边界和回应速度，不急着用一次谈话解决所有问题。"
        elif "事业" in question or "工作" in question:
            angle = "工作上适合把复杂目标拆小，用一个可验证动作争取主动权。"
        elif "财富" in question or "钱" in question:
            angle = "财务相关事项先核对信息和期限，避免为了情绪价值增加支出。"
        else:
            angle = f"今天最值得看的不是好坏，而是{lead_theme}如何改变你的选择顺序。"

        return f"{lead_description} 因此，{angle} 当前较弱的是{weak_label}，建议把承诺收窄到能完成的一步。"

    @staticmethod
    def _grounding(report: dict[str, Any]) -> list[str]:
        return [
            item.get("description", "")
            for item in (report.get("evidence") or [])[:3]
            if item.get("description")
        ]
