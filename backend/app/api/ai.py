# app/api/ai.py
from __future__ import annotations
from pydantic import BaseModel, Field
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

# Если generate_recommendations уже «прокинут» в services/ai_client.py — используем одну строку ниже:
from app.services.ai_client import list_models_ids, complete_text, generate_recommendations
# Если у тебя пока нет прокладки в services/ai_client.py, раскомментируй строку ниже и убери импорт выше:
# from app.ai import generate_recommendations

logger = logging.getLogger(__name__)

# Все AI-эндпоинты живут под /ai/*
router = APIRouter(prefix="/ai", tags=["AI"])


# ---------- Pydantic входные модели ----------
class CompleteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Текст запроса (не пустой)")
    model: str | None = Field(None, description="Название модели OpenAI")
    # Важно: минимум 16 токенов, максимум 8192, по умолчанию 300
    max_tokens: int | None = Field(
        300,
        ge=16,
        le=8192,
        description="Максимум токенов в ответе (не меньше 16)"
    )


class RecRequest(BaseModel):
    company_name: Optional[str] = None
    # Сюда передаем уже «ужатые» агрегаты 8 моделей (swot, pestel, porter, bcg, value_chain, canvas, unit_economics, bsc)
    models: Dict[str, Any]


# ---------- Эндпоинты ----------
@router.get("/health")
def ai_health():
    """
    Быстрая проверка связи с OpenAI: пытаемся получить несколько моделей.
    """
    try:
        models = list_models_ids(limit=5)
        return {"status": "ok", "models": models}
    except Exception:
        # Полный стек в логах, пользователю — коротко
        logger.exception("AI health check failed")
        raise HTTPException(status_code=503, detail="AI health failed")


@router.post("/complete")
def ai_complete(req: CompleteRequest):
    """
    Простой completion: отправляем prompt в выбранную модель и возвращаем текст.
    """
    try:
        if not req.prompt.strip():
            raise HTTPException(status_code=422, detail="Prompt must not be empty")

        # если модель не указана — пробуем из окружения; иначе используем легкую по умолчанию
        default_model = os.getenv("OPENAI_MODEL") or "o4-mini"
        model = req.model or default_model

        text = complete_text(
            prompt=req.prompt,
            model=req.model,
            max_output_tokens=req.max_tokens or 300,
        )
        return {"ok": True, "content": text}

    except HTTPException:
        # уже «правильная» ошибка — прокидываем
        raise

    except ValidationError:
        logger.exception("Validation error in /ai/complete")
        raise HTTPException(status_code=400, detail="Validation error")

    except TimeoutError:
        logger.exception("OpenAI timeout in /ai/complete")
        raise HTTPException(status_code=504, detail="AI timeout")

    except Exception:
        logger.exception("Unhandled error in /ai/complete")
        raise HTTPException(status_code=500, detail="AI complete error")


@router.post("/recommendations")
def ai_recommendations(req: RecRequest):
    """
    Главный эндпоинт: агрегированные результаты 8 моделей → структурированные рекомендации (строгий JSON).
    """
    try:
        data = generate_recommendations(req.models, req.company_name)
        return data

    except ValidationError:
        logger.exception("AI schema validation error in /ai/recommendations")
        raise HTTPException(status_code=502, detail="AI schema validation failed")

    except TimeoutError:
        logger.exception("OpenAI timeout in /ai/recommendations")
        raise HTTPException(status_code=504, detail="AI timeout")

    except Exception:
        logger.exception("Unhandled error in /ai/recommendations")
        raise HTTPException(status_code=500, detail="AI generation error")

