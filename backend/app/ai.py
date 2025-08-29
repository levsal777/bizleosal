# app/ai.py
from __future__ import annotations
import os, json
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, conint, confloat, ValidationError
from openai import OpenAI

# ---------- Pydantic-модели (локальная валидация) ----------
class KPI(BaseModel):
    name: str
    target: str

class RecItem(BaseModel):
    id: str
    # overall|swot|pestel|porter|bcg|value_chain|canvas|unit_economics|bsc
    area: str
    title: str
    rationale: str
    steps: List[str] = Field(default_factory=list)
    impact: conint(ge=1, le=5)
    effort: conint(ge=1, le=5)
    confidence: confloat(ge=0, le=1)
    priority_score: confloat(ge=0)
    horizon: str = Field(description="short|medium|long")
    kpis: List[KPI] = Field(default_factory=list)

class PerModelAdvice(BaseModel):
    summary: str
    top_issues: List[str] = Field(default_factory=list)
    actions: List[RecItem] = Field(default_factory=list)

class Recommendations(BaseModel):
    summary: str
    recommendations: List[RecItem]
    by_model: Dict[str, PerModelAdvice]
    scores: Dict[str, float] | None = None

# ---------- JSON Schema для Structured Outputs ----------
OUTPUT_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "recommendations": {"type": "array", "items": {"$ref": "#/$defs/RecItem"}},
        "by_model": {
            "type": "object",
            "properties": {
                "swot": {"$ref": "#/$defs/PerModelAdvice"},
                "pestel": {"$ref": "#/$defs/PerModelAdvice"},
                "porter": {"$ref": "#/$defs/PerModelAdvice"},
                "bcg": {"$ref": "#/$defs/PerModelAdvice"},
                "value_chain": {"$ref": "#/$defs/PerModelAdvice"},
                "canvas": {"$ref": "#/$defs/PerModelAdvice"},
                "unit_economics": {"$ref": "#/$defs/PerModelAdvice"},
                "bsc": {"$ref": "#/$defs/PerModelAdvice"}
            },
            "additionalProperties": False
        },
        "scores": {
            "type": "object",
            "properties": {
                "porter": {"type": "number"},
                "bsc": {"type": "number"},
                "unit_economics": {"type": "number"},
                "overall": {"type": "number"}
            },
            "additionalProperties": True
        }
    },
    "required": ["summary", "recommendations", "by_model"],
    "additionalProperties": False,
    "$defs": {
        "KPI": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "target": {"type": "string"}},
            "required": ["name", "target"],
            "additionalProperties": False
        },
        "RecItem": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "area": {
                    "type": "string",
                    "enum": [
                        "overall","swot","pestel","porter","bcg",
                        "value_chain","canvas","unit_economics","bsc"
                    ]
                },
                "title": {"type": "string"},
                "rationale": {"type": "string"},
                "steps": {"type": "array", "items": {"type": "string"}},
                "impact": {"type": "integer", "minimum": 1, "maximum": 5},
                "effort": {"type": "integer", "minimum": 1, "maximum": 5},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "priority_score": {"type": "number", "minimum": 0},
                "horizon": {"type": "string", "enum": ["short","medium","long"]},
                "kpis": {"type": "array", "items": {"$ref": "#/$defs/KPI"}}
            },
            "required": [
                "id","area","title","rationale","steps",
                "impact","effort","confidence","priority_score","horizon"
            ],
            "additionalProperties": False
        },
        "PerModelAdvice": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "top_issues": {"type": "array", "items": {"type": "string"}},
                "actions": {"type": "array", "items": {"$ref": "#/$defs/RecItem"}}
            },
            "required": ["summary","actions"],
            "additionalProperties": False
        }
    }
}

# ---------- Ключ и клиент ----------
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = (
    "Ты бизнес-аналитик мирового уровня. На основе итогов восьми моделей "
    "(SWOT, PESTEL, Porter, BCG, Value Chain, Canvas, Unit Economics, BSC) "
    "сформируй приоритезированные рекомендации. "
    "Всегда считай priority_score формулой round(impact*confidence/effort, 2). "
    "Кратко и по делу. Язык: русский. "
    "Возвращай только JSON строго по схеме, без пояснений."
)

def _build_user_payload(company_name: Optional[str], models: dict) -> str:
    payload = {"company": company_name or "Без названия", "models": models}
    return json.dumps(payload, ensure_ascii=False)

def _extract_json(text: str) -> dict:
    """
    Берём подстроку от первой '{' до последней '}' и парсим JSON.
    Если JSON не найден — бросаем исключение.
    """
    if not isinstance(text, str):
        text = str(text or "")
    s = text.strip()
    i, j = s.find("{"), s.rfind("}")
    if i == -1 or j == -1 or j <= i:
        raise ValueError("Model returned no JSON object")
    return json.loads(s[i:j + 1])

def _coerce_for_schema(data: dict) -> dict:
    """
    Приводим ответ модели к нашей схеме Recommendations.
    Поддерживаем алиасы: action->title, why|reason->rationale, how|plan->steps.
    Клэмпим числа, заполняем дефолты, считаем priority_score если нет.
    """
    if not isinstance(data, dict):
        return {"summary": str(data), "recommendations": [], "by_model": {}}

    out = dict(data)

    # верхний уровень
    if not isinstance(out.get("summary"), str):
        out["summary"] = str(out.get("summary") or "")
    recs = out.get("recommendations")
    if not isinstance(recs, list):
        recs = [recs] if isinstance(recs, (dict, str)) else []
    bm = out.get("by_model")
    if not isinstance(bm, dict):
        bm = {}
    out["by_model"] = bm

    fixed_recs = []
    for idx, r in enumerate(recs, start=1):
        if isinstance(r, str):
            r = {"title": r}
        if not isinstance(r, dict):
            continue
        rr = dict(r)

        # алиасы
        if "title" not in rr and "action" in rr:
            rr["title"] = rr.get("action")
        if "rationale" not in rr:
            rr["rationale"] = rr.get("why") or rr.get("reason") or ""
        steps = rr.get("steps", rr.get("how") or rr.get("plan"))
        if isinstance(steps, list):
            rr["steps"] = [str(s) for s in steps]
        elif isinstance(steps, str) and steps.strip():
            parts = [p.strip() for p in steps.replace(";", ".").split(".") if p.strip()]
            rr["steps"] = parts
        else:
            rr["steps"] = []

        rr["id"] = str(rr.get("id") or f"rec-{idx}")
        rr["area"] = str(rr.get("area") or "overall")
        rr["title"] = str(rr.get("title") or "")
        rr["rationale"] = str(rr.get("rationale") or "")

        def _clampi(x, lo, hi, default):
            try:
                v = int(x)
            except Exception:
                v = default
            return max(lo, min(hi, v))

        def _clampf(x, lo, hi, default):
            try:
                v = float(x)
            except Exception:
                v = default
            return max(lo, min(hi, v))

        rr["impact"] = _clampi(rr.get("impact"), 1, 5, 3)
        rr["effort"] = _clampi(rr.get("effort"), 1, 5, 3)
        rr["confidence"] = _clampf(rr.get("confidence"), 0.0, 1.0, 0.7)

        hz = str(rr.get("horizon") or "short")
        if hz not in ("short", "medium", "long"):
            hz = "short"
        rr["horizon"] = hz

        kpis = rr.get("kpis")
        rr["kpis"] = kpis if isinstance(kpis, list) else []

        try:
            ps = float(rr.get("priority_score")) if rr.get("priority_score") is not None else None
        except Exception:
            ps = None
        if ps is None:
            ps = round(rr["impact"] * rr["confidence"] / max(1, rr["effort"]), 2)
        rr["priority_score"] = ps

        fixed_recs.append(rr)
    out["recommendations"] = fixed_recs

    # by_model упрощённая нормализация
    def _fix_advice(x):
        if not isinstance(x, dict):
            return {"summary": "", "top_issues": [], "actions": []}
        y = dict(x)
        if not isinstance(y.get("summary"), str): y["summary"] = str(y.get("summary") or "")
        if not isinstance(y.get("top_issues"), list): y["top_issues"] = []
        if not isinstance(y.get("actions"), list):
            y["actions"] = [str(y["actions"])] if isinstance(y.get("actions"), str) else []
        return y

    for key in ("swot","pestel","porter","bcg","value_chain","canvas","unit_economics","bsc"):
        if key in out["by_model"]:
            out["by_model"][key] = _fix_advice(out["by_model"][key])

    # scores — если есть, должен быть объектом
    if "scores" in out and not isinstance(out["scores"], dict):
        out["scores"] = {}

    return out

def generate_recommendations(models: dict, company_name: Optional[str] = None) -> dict:
    """
    models: словарь итогов 8 моделей (агрегаты, не сырые логи).
    return: dict строго по OUTPUT_JSON_SCHEMA.
    """
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    max_tokens = max(16, int(os.getenv("OPENAI_MAX_TOKENS", "1200")))
    user_content = _build_user_payload(company_name, models)

    resp = _client.responses.create(
        model=model_name,
        input=f"{SYSTEM_PROMPT}\n\nПОЛЬЗОВАТЕЛЬ: {user_content}\n\nВерни только JSON строго по схеме без пояснений.",
        temperature=0.2,
        max_output_tokens=max_tokens,
    )

    text = getattr(resp, "output_text", "") or ""
    try:
        data = _extract_json(text)
    except Exception as e:
        raise RuntimeError(f"LLM вернула не-JSON: {text[:160]}...") from e

    # Мягкая нормализация перед строгой валидацией
    data = _coerce_for_schema(data)

    # Строгая валидация схемой Pydantic
    try:
        validated = Recommendations.model_validate(data)
        return validated.model_dump()
    except ValidationError as ve:
        raise RuntimeError(f"LLM вернула JSON не по схеме: {ve}") from ve

