from math import isfinite
from typing import List
from app.schemas.recommendations import (
    AiCompleteRequest, AiCompleteResponse, RecItem, KPI, Meta
)
from app.clients.llm_client import generate_raw_recommendations

def _score(impact: int, effort: int) -> float:
    # простая метрика приоритета: impact / effort
    val = impact / max(effort, 1)
    return round(val, 3)

async def build_recommendations(payload: AiCompleteRequest) -> AiCompleteResponse:
    raw = await generate_raw_recommendations(payload)

    items: List[RecItem] = []
    for i, r in enumerate(raw["items"], start=1):
        item = RecItem(
            id=r.get("id") or f"rec_{i:03d}",
            area=r["area"],
            title=r["title"],
            rationale=r["rationale"],
            steps=r.get("steps", [])[:10],
            impact=r.get("impact", 3),
            effort=r.get("effort", 2),
        )
        item.priority = _score(item.impact, item.effort)
        items.append(item)

    # сортируем по приоритету убыв.
    items.sort(key=lambda x: x.priority, reverse=True)
    items = items[: payload.limit]

    kpis = [KPI(name=k["name"], target=k["target"]) for k in raw.get("kpis", [])]

    return AiCompleteResponse(
        items=items,
        kpis=kpis,
        meta=Meta(model=raw.get("model"))
    )

