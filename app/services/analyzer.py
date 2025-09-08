from typing import Any, Dict
from app.domain.models8 import run_all_models

def run_all(company_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    models = run_all_models(payload or {})
    return {
        "company_id": company_id,
        "status": "ok",
        "models_count": len(models),
        "results": models,
        "note": "Скелет анализа готов. Следующий шаг — подключить реальные формулы и приоритизацию.",
    }
