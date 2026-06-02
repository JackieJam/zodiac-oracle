from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from xingzuo.astro_engine import AstroContext, AstroFactor


AREAS = ["career", "relationship", "wealth", "wellness"]
AREA_NAMES = {
    "career": "事业",
    "relationship": "关系",
    "wealth": "财富",
    "wellness": "身心",
}

THEME_TO_AREA = {
    "自我表达": "career",
    "领导力": "career",
    "长期方向": "career",
    "情绪节奏": "wellness",
    "家庭关系": "relationship",
    "安全感": "wellness",
    "沟通判断": "career",
    "学习效率": "career",
    "合同文书": "wealth",
    "亲密关系": "relationship",
    "审美消费": "wealth",
    "合作氛围": "relationship",
    "行动力": "career",
    "竞争压力": "career",
    "身体能量": "wellness",
    "机会扩张": "wealth",
    "贵人资源": "career",
    "信念感": "wellness",
    "现实考验": "career",
    "结构压力": "wellness",
    "长期承诺": "relationship",
    "变化突破": "career",
    "直觉想象": "wellness",
    "深层转化": "wellness",
}


@dataclass(frozen=True)
class Forecast:
    context: AstroContext
    scores: dict[str, int]
    overall_score: int
    highlights: list[str]
    actions: list[str]
    evidence: list[dict[str, Any]]
    generated_at: datetime


class ForecastRuleEngine:
    # 分数含义:
    #   0-39  凶  — 重大压力，宜守不宜攻
    #  40-49  弱  — 阻力明显，需谨慎行事
    #  50-59  平  — 中性日常，维持节奏即可
    #  60-69  稳  — 略有助力，可适度推进
    #  70-79  顺  — 信号积极，适合主动出击
    #  80-100 吉  — 强力支撑，抓住机会发力

    def score(self, context: AstroContext) -> Forecast:
        raw_scores = {area: 50.0 for area in AREAS}
        for factor in context.factors:
            area = THEME_TO_AREA.get(factor.theme, "career")
            raw_scores[area] += self._factor_delta(factor)

        scores = {area: int(max(20, min(95, round(value)))) for area, value in raw_scores.items()}
        overall = int(round(sum(scores.values()) / len(scores)))
        leading = sorted(context.factors, key=lambda item: item.weight, reverse=True)[:3]
        highlights = [self._highlight_for(factor) for factor in leading]
        actions = self._actions_for(scores, leading)
        evidence = [
            {
                "planet": factor.planet,
                "aspect": factor.aspect,
                "aspect_cn": factor.aspect_cn,
                "target": factor.target,
                "orb": factor.orb,
                "theme": factor.theme,
                "polarity": factor.polarity,
                "confidence": factor.weight,
                "description": factor.description,
            }
            for factor in context.factors
        ]
        return Forecast(
            context=context,
            scores=scores,
            overall_score=overall,
            highlights=highlights,
            actions=actions,
            evidence=evidence,
            generated_at=datetime.now(),
        )

    @staticmethod
    def _factor_delta(factor: AstroFactor) -> float:
        # weight: 0.2-1.0 (基于容许度与最大容许度的比值)
        # 支撑相位(拱/六合): 正向调整
        # 压力相位(刑/冲): 等量负向调整，不打折
        # 中性相位(合相): 轻微正向(取决于参与行星)
        base = factor.weight * 15
        if factor.polarity == "supportive":
            return base
        if factor.polarity == "challenging":
            return -base
        return base * 0.2

    @staticmethod
    def _highlight_for(factor: AstroFactor) -> str:
        if factor.polarity == "supportive":
            return f"{factor.theme}得到推进，适合主动争取资源或表达真实想法。"
        if factor.polarity == "challenging":
            return f"{factor.theme}容易出现拉扯，先确认边界和节奏再推进。"
        return f"{factor.theme}处在转换点，适合观察信号并做小幅调整。"

    @staticmethod
    def _actions_for(scores: dict[str, int], factors: list[AstroFactor]) -> list[str]:
        weakest_area = min(scores, key=scores.get)
        strongest_area = max(scores, key=scores.get)
        primary_theme = factors[0].theme if factors else "日常节奏"
        return [
            f"把今天最重要的决定放在{AREA_NAMES[strongest_area]}相关事项上，顺势推进。",
            f"{AREA_NAMES[weakest_area]}分数偏低，避免情绪化承诺，先做信息核对。",
            f"围绕{primary_theme}安排一个可执行的小动作，不要一次性拉满。",
        ]
