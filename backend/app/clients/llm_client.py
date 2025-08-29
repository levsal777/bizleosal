from typing import Dict, Any, List, Optional, Union

# from openai import OpenAI  # подключите, когда будете готовы

def _get(obj: Union[dict, Any], path: str, default=None):
    """Безопасно достаем поле из Pydantic-модели или dict: 'company.name' и т.п."""
    cur = obj
    for part in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur if cur is not None else default

def _clamp_score(x: Any) -> int:
    """Переводим в число и ограничиваем в диапазоне 1..5."""
    try:
        v = int(round(float(x)))
    except Exception:
        v = 3
    return max(1, min(5, v))

def _priority(impact: int, effort: int) -> float:
    return round(impact / max(1, effort), 1)

async def generate_raw_recommendations(payload) -> Dict[str, Any]:
    """
    Заглушка LLM. Возвращает структуру:
    {
      "model": "demo",
      "items": [{ area, title, rationale, steps, impact, effort, priority }],
      "kpis": [{ name, target }]
    }
    """
    # 1) Считаем входные данные
    company_name: str = _get(payload, "company.name", "") or "Компания"
    industry: str = (_get(payload, "company.industry", "") or "").lower()
    context: str = _get(payload, "context", "") or ""
    chosen_models: List[str] = _get(payload, "models", []) or []
    goals: List[str] = _get(payload, "goals", []) or []

    # 2) Набор базовых рекомендаций (минимум две — как у тебя было)
    base_items = [
        {
            "area": "swot",
            "title": "Усилить сильные стороны в онлайн-воронке",
            "rationale": "SWOT показал сильный органический трафик, но слабую конверсию.",
            "steps": ["Upsell в корзине", "Лид-магнит на страницах услуг"],
            "impact": 5, "effort": 2,
        },
        {
            "area": "unit_economics",
            "title": "Снизить CAC на 15%",
            "rationale": "LTV/CAC < 3 на платном трафике; есть резерв в креативах.",
            "steps": ["A/B-тест офферов", "Единые UTM-метки во всех кампаниях"],
            "impact": 4, "effort": 2,
        },
    ]

    # 3) Лёгкая персонализация по контексту (без «магии» — просто приятный штрих)
    ctx = context.lower()
    if "кофе" in ctx or "кофей" in ctx:
        base_items.append({
            "area": "value_chain",
            "title": "Повысить маржу на напитках за счёт оптимизации закупок",
            "rationale": "В сети кофеен сильная зависимость от закупочных цен и потерь.",
            "steps": ["Сравнить 3 поставщиков", "Стандартизировать рецептуры", "Ввести контроль списаний"],
            "impact": 4, "effort": 3,
        })
    if "конкуренц" in ctx:
        base_items.append({
            "area": "porter",
            "title": "Дифференцироваться за счёт уникального оффера",
            "rationale": "Высокая конкуренция — усилить барьеры смены и ценность для клиента.",
            "steps": ["Ввести гарантию результата", "Уникальные бандлы/подписка"],
            "impact": 4, "effort": 3,
        })

    # 4) Фильтр по выбранным моделям (если фронт прислал список)
    if chosen_models:
        base_items = [it for it in base_items if it["area"] in chosen_models]

    # 5) Аккуратная нормализация и приоритет
    items_normalized = []
    for it in base_items:
        impact = _clamp_score(it.get("impact"))
        effort = _clamp_score(it.get("effort"))
        it2 = {
            "area": it["area"],
            "title": it["title"].strip(),
            "rationale": it["rationale"].strip(),
            "steps": [s.strip() for s in (it.get("steps") or [])][:8],  # ограничим до 8 шагов
            "impact": impact,
            "effort": effort,
            "priority": _priority(impact, effort),
        }
        items_normalized.append(it2)

    # 6) Простые KPI — под отрасль или по умолчанию
    kpis: List[Dict[str, str]] = [
        {"name": "CR сайта", "target": "≥ 2.5%"},
        {"name": "CAC", "target": "≤ 1500 ₽"},
    ]
    if "retail" in industry:
        kpis = [
            {"name": "Конверсия в покупку (офлайн+онлайн)", "target": "≥ 25%/сессию"},
            {"name": "Средний чек", "target": "+10% к текущему"},
        ]

    # 7) Лёгкий приоритет по целям (если среди целей рост выручки — ставим повыше impact)
    if any("рост выручки" in g.lower() for g in goals):
        items_normalized.sort(key=lambda x: (x["impact"], -x["effort"]), reverse=True)
    else:
        items_normalized.sort(key=lambda x: x["priority"], reverse=True)

    return {
        "model": "demo",
        "items": items_normalized,
        "kpis": kpis,
    }

