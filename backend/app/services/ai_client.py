from typing import List, Optional, Dict, Any
from openai import OpenAI
from app.core.config import settings
import json

# ---------- Инициализация клиента (как у тебя) ----------
_client_kwargs = {"api_key": settings.OPENAI_API_KEY}
if getattr(settings, "OPENAI_BASE_URL", None):
    _client_kwargs["base_url"] = settings.OPENAI_BASE_URL
if getattr(settings, "OPENAI_ORG", None):
    _client_kwargs["organization"] = settings.OPENAI_ORG

client = OpenAI(**_client_kwargs)

DEFAULT_MODEL = getattr(settings, "OPENAI_MODEL", None) or "o4-mini"  # можно поменять из .env

# ---------- Вспомогательные ----------
def list_models_ids(limit: int = 10) -> List[str]:
    """
    Проверка доступа к OpenAI: вернём несколько id моделей.
    ВАЖНО: если используешь Azure/OpenAI-прокси, .models.list() может быть недоступен — тогда читай из конфига.
    """
    data = client.models.list().data
    return [m.id for m in data[:limit]]

# ---------- Рекомендованный способ: Responses API ----------
def complete_text(prompt: str, model: Optional[str] = None, max_output_tokens: int = 300) -> str:
    """
    Короткая текстовая генерация без структуры.
    Почему Responses API: официально рекомендуемый путь, доступен удобный output_text.
    """
    resp = client.responses.create(
        model=model or DEFAULT_MODEL,
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": "You are a helpful assistant."}]},
            {"role": "user",   "content": [{"type": "input_text", "text": prompt}]}
        ],
        temperature=0.2,
        max_output_tokens=max_output_tokens,  # для Responses API используем max_output_tokens
    )
    return resp.output_text or ""

def complete_json(
    instructions: str,
    user_payload: Dict[str, Any],
    json_schema: Dict[str, Any],
    model: Optional[str] = None,
    max_output_tokens: int = 800
) -> Dict[str, Any]:
    """
    Строгий структурированный вывод по JSON-схеме.
    Возвращает dict, валидный по заданной схеме (strict:true).
    """
    resp = client.responses.create(
        model=model or DEFAULT_MODEL,
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
            {"role": "user",   "content": [{"type": "input_text", "text": json.dumps(user_payload, ensure_ascii=False)}]}
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "StrictOutput",
                "strict": True,
                "schema": json_schema
            }
        },
        temperature=0.2,
        max_output_tokens=max_output_tokens,
    )
    return json.loads(resp.output_text or "{}")

from app.ai import generate_recommendations

__all__ = ["list_models_ids", "complete_text", "complete_json", "generate_recommendations"]

