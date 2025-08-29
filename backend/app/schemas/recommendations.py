from typing import List, Optional, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, conint, confloat, constr

Area = Literal["overall","swot","pestel","porter","bcg","value_chain","canvas","unit_economics","bsc"]
Lang = Literal["ru","en"]

# ====== REQUEST ======
class Company(BaseModel):
    name: constr(min_length=1, max_length=200)
    industry: Optional[constr(min_length=2, max_length=64)] = None
    region: Optional[constr(min_length=2, max_length=32)] = None

class AiCompleteRequest(BaseModel):
    company: Company
    goals: List[constr(min_length=1, max_length=120)] = Field(default_factory=list, max_items=20)
    models: List[Area] = Field(default_factory=list, max_items=8)
    limit: conint(ge=1, le=20) = 7
    lang: Lang = "ru"
    client_request_id: Optional[UUID] = None
    context: Optional[constr(max_length=2000)] = None  
# ====== RESPONSE ======
class KPI(BaseModel):
    name: constr(min_length=1, max_length=80)
    target: constr(min_length=1, max_length=80)

class RecItem(BaseModel):
    id: constr(min_length=1, max_length=60)
    area: Area
    title: constr(min_length=1, max_length=140)
    rationale: constr(min_length=1, max_length=2000)
    steps: List[constr(min_length=1, max_length=240)] = Field(default_factory=list, max_items=10)
    impact: conint(ge=1, le=5)
    effort: conint(ge=1, le=5)
    priority: confloat(ge=0) = 0.0  # вычисляем на бэке

class Meta(BaseModel):
    version: str = "1.0.0"
    generated_at: Optional[str] = None
    model: Optional[str] = None
    trace_id: str = Field(default_factory=lambda: str(uuid4()))

class AiCompleteResponse(BaseModel):
    items: List[RecItem]
    kpis: List[KPI] = Field(default_factory=list)
    meta: Meta = Meta()

# ====== ERROR (RFC7807-like) ======
class ErrorResponse(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: Optional[str] = None
    trace_id: str = Field(default_factory=lambda: str(uuid4()))

