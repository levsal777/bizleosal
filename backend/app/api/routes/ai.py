from fastapi import APIRouter, HTTPException, status, Request
from datetime import datetime, timezone
from ...schemas.recommendations import (
    AiCompleteRequest, AiCompleteResponse, RecItem, KPI, Meta, ErrorResponse
)
from ...services.recommendation_service import build_recommendations

router = APIRouter(prefix="/v1/ai", tags=["ai"])

@router.post(
    "/complete",
    response_model=AiCompleteResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Сгенерировать рекомендации по 8 моделям",
)
async def ai_complete(req: Request, payload: AiCompleteRequest) -> AiCompleteResponse:
    try:
        resp = await build_recommendations(payload)
        resp.meta.generated_at = datetime.now(timezone.utc).isoformat()
        return resp
    except ValueError as e:
        # наши контролируемые ошибки
        return ErrorResponse(
            title="Bad Request",
            status=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )  # FastAPI сам проставит код, если поднять HTTPException
    except Exception as e:
        # логирование перехватим в middleware/логгере
        raise HTTPException(status_code=500, detail="Internal Server Error")

