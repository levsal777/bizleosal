from __future__ import annotations
from typing import List, Dict, Any
import os, json, pathlib

# --- простая подгрузка /app/.env без сторонних библиотек ---
def _load_env_file(path: str = "/app/.env") -> None:
    p = pathlib.Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip("'\"")
        # не затираем уже установленные переменные окружения
        os.environ.setdefault(k, v)

_load_env_file()

# Дефолтные веса по областям
DEFAULT_AREA_WEIGHTS: Dict[str, float] = {
    "overall": 1.05,
    "swot": 1.00,
    "pestel": 0.90,
    "porter": 1.05,
    "bcg": 1.00,
    "value_chain": 1.05,
    "canvas": 0.95,
    "unit_economics": 1.15,
    "bsc": 1.10,
}
KNOWN_AREAS = set(DEFAULT_AREA_WEIGHTS.keys())

# Параметры расчёта
SCORE_BASE = 100
IMPACT_STEP = 12
EFFORT_STEP = 6
SCORE_MIN = 70.0
SCORE_MAX = 140.0

WEIGHT_MIN = 0.5
WEIGHT_MAX = 2.0

def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v

def _priority_base(impact: int, effort: int) -> float:
    return SCORE_BASE + (impact - 3) * IMPACT_STEP - (effort - 3) * EFFORT_STEP

def _merge_weights_from_env(base: Dict[str, float]) -> Dict[str, float]:
    weights = dict(base)
    raw = os.getenv("AREA_WEIGHTS") or os.getenv("AREA_WEIGHTS_JSON")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, (int, float)):
                        k_norm = str(k).strip().lower()
                        if k_norm in KNOWN_AREAS:
                            weights[k_norm] = float(_clamp(float(v), WEIGHT_MIN, WEIGHT_MAX))
        except Exception:
            pass
    for area in base:
        env_name = "WEIGHT_" + area.upper()
        val = os.getenv(env_name)
        if val is None:
            continue
        try:
            f = float(val)
            weights[area] = float(_clamp(f, WEIGHT_MIN, WEIGHT_MAX))
        except Exception:
            pass
    return weights

def _sanitize_item(raw: Dict[str, Any], weights: Dict[str, float]) -> Dict[str, Any]:
    area = str(raw.get("area", "overall")).strip().lower()
    if area not in KNOWN_AREAS:
        area = "overall"
    try: impact = int(raw.get("impact", 3))
    except Exception: impact = 3
    try: effort = int(raw.get("effort", 3))
    except Exception: effort = 3
    impact = int(_clamp(impact, 1, 5))
    effort = int(_clamp(effort, 1, 5))
    title = str(raw.get("title", "")).strip()[:200]
    rationale = str(raw.get("rationale", "")).strip()
    steps = raw.get("steps", []); 
    if not isinstance(steps, list): steps = [str(steps)]
    base = _priority_base(impact, effort)
    weighted = base * weights.get(area, 1.0)
    score = round(_clamp(weighted, SCORE_MIN, SCORE_MAX), 1)
    return {
        "area": area, "title": title, "rationale": rationale, "steps": steps,
        "impact": impact, "effort": effort, "priority_score": score,
    }

def _priority_score(impact: int, effort: int, area: str = "overall") -> float:
    weights = _merge_weights_from_env(DEFAULT_AREA_WEIGHTS)
    area = area if area in KNOWN_AREAS else "overall"
    base = _priority_base(int(_clamp(impact, 1, 5)), int(_clamp(effort, 1, 5)))
    weighted = base * weights.get(area, 1.0)
    return round(_clamp(weighted, SCORE_MIN, SCORE_MAX), 1)

def generate_default(company: Dict | None = None, limit: int = 12) -> List[Dict]:
    name = (company or {}).get("name", "компания")
    industry = (company or {}).get("industry", "бизнес")
    region = (company or {}).get("region", "регион")

    items: List[Dict] = []
    items.append({"area":"overall","title":f"Запустить перформанс-маркетинг для {industry}",
                  "rationale":f"Нужно ускорить поток лидов в {region} без роста постоянных издержек.",
                  "steps":["VK/РСЯ","ретаргет","сквозная аналитика","управление CPL/CPA"],"impact":5,"effort":3})
    items.extend([
        {"area":"swot","title":"Усилить сильные стороны в УТП",
         "rationale":"Фокус на 1–2 ключевых преимуществах повышает конверсию лендинга/объявлений.",
         "steps":["Собрать отзывы","Вынести факты на первый экран","A/B-тест 2-3 заголовков"],"impact":4,"effort":2},
        {"area":"swot","title":"Закрыть операционную слабость в обработке заявок",
         "rationale":"Потери лидов из-за просроченных ответов >15 минут.",
         "steps":["Внедрить автоворонки","SLA 5-10 минут","Шаблоны ответов"],"impact":4,"effort":2},
    ])
    items.append({"area":"pestel","title":"Снизить чувствительность к внешним колебаниям",
                  "rationale":"Колебания спроса и цены на трафик — диверсифицируем каналы.",
                  "steps":["SEO-ядро","Контент-план на 8 недель","Реферальная программа"],"impact":4,"effort":3})
    items.append({"area":"porter","title":"Перехват спроса у конкурентов",
                  "rationale":"Точки входа: бренд-запросы конкурентов, look-alike аудитории, прайс-якоря.",
                  "steps":["Собрать 10 конкурентов","Рекламные группы по брендам","Сравнительные креативы"],"impact":5,"effort":3})
    items.append({"area":"bcg","title":"Вывести 1 услугу в «звёзды»",
                  "rationale":"Сконцентрировать бюджет на лид-магните с лучшей unit-экономикой.",
                  "steps":["Рассчитать CAC/LTV","Выбрать лид-магнит","Сместить 30–40% бюджета"],"impact":4,"effort":2})
    items.append({"area":"value_chain","title":"Укоротить путь клиента на 1 шаг",
                  "rationale":"Каждый лишний шаг — минус конверсия. Убираем трение.",
                  "steps":["Кнопка записи в 1 клик","Предзаполненные формы","Автоуведомления"],"impact":4,"effort":2})
    items.append({"area":"canvas","title":"Переписать ценностное предложение (Canvas)",
                  "rationale":"Простой язык, выгоды и доказательства — рост CR лендинга/объявлений.",
                  "steps":["Формула «боль-решение-доказательство»","2 версии лендинга","A/B-тест"],"impact":4,"effort":2})
    items.extend([
        {"area":"unit_economics","title":"Снизить COGS на 5–7%",
         "rationale":"Пересмотр закупок/логистики, оптовые условия.",
         "steps":["Список топ-поставщиков","Переговоры","Пилот на 1 категории"],"impact":4,"effort":2},
        {"area":"unit_economics","title":"Поднять средний чек через бандлы",
         "rationale":"Бандлы и допродажи дают +8–15% к выручке без увеличения трафика.",
         "steps":["3 бандла","Кросс-селл на чеке","Скрипты для менеджера"],"impact":4,"effort":2},
    ])
    items.append({"area":"bsc","title":"Ввести еженедельный дашборд KPI",
                  "rationale":"Прозрачность: лиды, CR, CAC, LTV, GM, NPS.",
                  "steps":["Собрать метрики","Стэндап 20 минут","Цели на неделю"],"impact":5,"effort":2})

    weights = _merge_weights_from_env(DEFAULT_AREA_WEIGHTS)
    sanitized = [_sanitize_item(it, weights) for it in items]
    limit = max(1, min(limit, len(sanitized)))
    return sanitized[:limit]
