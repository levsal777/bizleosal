from typing import Any, Dict, Optional
from fastapi import APIRouter, Path
from pydantic import BaseModel
from app.services.analyzer import run_all

router = APIRouter()

class AnalysisInput(BaseModel):
    data: Optional[Dict[str, Any]] = {}

@router.post("/{company_id}/analysis/run")
def run_analysis(company_id: int = Path(..., ge=1), body: AnalysisInput | None = None):
    payload = body.data if body and body.data else {}
    return run_all(company_id, payload)
