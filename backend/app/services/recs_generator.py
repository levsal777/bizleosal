from __future__ import annotations
import os, json
from typing import Dict, Any

DEFAULT_AREA_WEIGHTS: Dict[str, float] = {
    "overall": 1.0,
    "swot": 1.0,
    "pestel": 1.0,
    "porter": 1.0,
    "bcg": 1.0,
    "value_chain": 1.0,
    "canvas": 1.0,
    "unit_economics": 1.0,
    "bsc": 1.0,
}

def _merge_weights_from_env(base: Dict[str, float] | None = None) -> Dict[str, float]:
    base = dict(base or DEFAULT_AREA_WEIGHTS)
    raw = os.getenv("AREA_WEIGHTS")
    if not raw:
        return base
    try:
        custom = json.loads(raw)
        if isinstance(custom, dict):
            for k, v in custom.items():
                try:
                    base[k] = float(v)
                except Exception:
                    pass
    except Exception:
        pass
    return base

def _sanitize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    area = (item.get("area") or "").strip() or "overall"
    title = (item.get("title") or "").strip() or "Без названия"
    rationale = (item.get("rationale") or "").strip()
    steps = list(item.get("steps") or [])
    try:
        impact = int(item.get("impact", 3))
    except Exception:
        impact = 3
    try:
        effort = int(item.get("effort", 3))
    except Exception:
        effort = 3
    impact = min(5, max(1, impact))
    effort = min(5, max(1, effort))
    return {
        "area": area,
        "title": title,
        "rationale": rationale,
        "steps": steps,
        "impact": impact,
        "effort": effort,
    }

__all__ = ["DEFAULT_AREA_WEIGHTS", "_merge_weights_from_env", "_sanitize_item"]
