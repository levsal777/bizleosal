from ..services.recs_generator import _sanitize_item, _merge_weights_from_env, DEFAULT_AREA_WEIGHTS
from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field, conint
from typing import Optional, List, Literal, Any, Dict
from app.db import get_conn
from app.utils.sorting import apply_sorting
import json

router = APIRouter(prefix="/companies", tags=["companies"])

# --------- Pydantic-модели ---------

class CompanyCreate(BaseModel):
    name: str = Field(..., max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None

class CompanyOut(BaseModel):
    id: int
    name: str
    industry: Optional[str]
    region: Optional[str]
    description: Optional[str]

ModelName = Literal[
    "swot","pestel","porter","bcg","value_chain","canvas","unit_economics","bsc"
]

class AnalysisCreate(BaseModel):
    model: ModelName
    input_data: Optional[Dict[str, Any]] = None

class AnalysisOut(BaseModel):
    id: int
    company_id: int
    model: ModelName

AreaName = Literal[
    "overall","swot","pestel","porter","bcg","value_chain","canvas","unit_economics","bsc"
]

class RecommendationIn(BaseModel):
    area: AreaName
    title: str = Field(..., max_length=255)
    rationale: Optional[str] = None
    steps: Optional[List[str]] = None
    impact: conint(ge=1, le=5)
    effort: conint(ge=1, le=5)
    priority_note: Optional[str] = None
    analysis_id: Optional[int] = None

class RecommendationCreated(BaseModel):
    id: int
    area: AreaName
    title: str
    impact: int
    effort: int
    priority_score: float

class RecommendationOut(BaseModel):
    id: int
    area: AreaName
    title: str
    impact: conint(ge=1, le=5)
    effort: conint(ge=1, le=5)

class KPIOut(BaseModel):
    id: int
    name: str
    unit: Optional[str]
    target_value: Optional[float]
    current_value: Optional[float]
    status: Optional[Literal["good","watch","bad"]]

# --------- Роуты ---------

@router.post("", response_model=CompanyOut)
def create_company(body: CompanyCreate, sort: str | None = Query(None, alias='sort')):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO company (name, industry, region, description)
                VALUES (%s, %s, %s, %s)
                RETURNING id, name, industry, region, description
                """,
                (body.name, body.industry, body.region, body.description),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(500, "Failed to create company")
            return {
                "id": row[0], "name": row[1], "industry": row[2],
                "region": row[3], "description": row[4]
            }

@router.get("", response_model=List[CompanyOut])
def list_companies(sort: str | None = Query(None, alias='sort')):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, industry, region, description FROM company ORDER BY id DESC"
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0], "name": r[1], "industry": r[2],
                    "region": r[3], "description": r[4]
                }
                for r in rows
            ]

@router.post("/{company_id}/analyses", response_model=AnalysisOut)
def create_analysis(company_id: int, body: AnalysisCreate, sort: str | None = Query(None, alias='sort')):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM company WHERE id=%s", (company_id,))
            if cur.fetchone() is None:
                raise HTTPException(404, "Company not found")

            input_json = json.dumps(body.input_data) if body.input_data else None
            cur.execute(
                """
                INSERT INTO analysis (company_id, model, input_data)
                VALUES (%s, %s, %s::jsonb)
                RETURNING id, company_id, model
                """,
                (company_id, body.model, input_json),
            )
            row = cur.fetchone()
            return {"id": row[0], "company_id": row[1], "model": row[2]}

@router.post("/{company_id}/recommendations/bulk", response_model=List[RecommendationCreated])
def create_recommendations_bulk(company_id: int, items: List[RecommendationIn], sort: str | None = Query(None, alias='sort')):
    # --- sanitizer: normalize & re-score before saving ---
    try:
        weights = _merge_weights_from_env(DEFAULT_AREA_WEIGHTS)
    except Exception:
        weights = DEFAULT_AREA_WEIGHTS
    _norm = []
    for _obj in items:
        try:
            raw = _obj.model_dump()
        except Exception:
            try:
                raw = _obj.dict()
            except Exception:
                raw = dict(_obj)
        clean = _sanitize_item(raw, weights)
        # пересобираем под входную схему
        _norm.append(RecommendationIn(**clean))  # type: ignore[name-defined]
    items = _norm
    # --- end sanitizer ---
    # 1) Пустой список — ничего не делаем
    if not items:
        return []

    with get_conn() as conn:
        with conn.cursor() as cur:
            # 2) Проверяем, что компания существует
            cur.execute("SELECT 1 FROM company WHERE id=%s", (company_id,))
            if cur.fetchone() is None:
                raise HTTPException(404, "Company not found")

            # 3) Готовим значения для массовой вставки
            payload = []
            for it in items:
                steps_json = json.dumps(it.steps) if getattr(it, "steps", None) else None
                payload.append((
                    company_id,
                    getattr(it, "analysis_id", None),
                    it.area,
                    it.title,
                    it.rationale,
                    steps_json,  # передаём как текст JSON; ниже приведём к jsonb
                    it.impact,
                    it.effort,
                    getattr(it, "priority_note", None),
                ))

            # 4) Ещё одна защита от пустого ввода
            if not payload:
                return []

            # 5) Строим VALUES с плейсхолдерами, 6-я колонка — явный CAST к jsonb
            row_ph = "(%s,%s,%s,%s,%s,CAST(%s AS jsonb),%s,%s,%s)"
            values_ph = ",".join([row_ph] * len(payload))

            sql = (
                "INSERT INTO recommendation "
                "(company_id, analysis_id, area, title, rationale, steps, impact, effort, priority_note) "
                f"VALUES {values_ph} "
                "RETURNING id, area, title, impact, effort, priority_score"
            )

            # 6) «Расплющиваем» список кортежей в один список параметров
            params = [v for row in payload for v in row]

            # 7) Выполняем и возвращаем результат
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [
                {
                    "id": r[0], "area": r[1], "title": r[2],
                    "impact": r[3], "effort": r[4],
                    "priority_score": float(r[5]) if r[5] is not None else 0.0
                }
                for r in rows
            ]

@router.get("/{company_id}/recommendations/top", response_model=List[RecommendationCreated])
def list_recommendations_top(company_id: int, limit: int = 20, sort: str | None = Query(None, alias='sort')):
    # простая защита от странных значений
    if limit < 1 or limit > 200:
        limit = 20
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, area, title, impact, effort, priority_score
                FROM recommendation
                WHERE company_id = %s
                ORDER BY priority_score DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (company_id, limit),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "area": r[1],
                    "title": r[2],
                    "impact": r[3],
                    "effort": r[4],
                    "priority_score": float(r[5]) if r[5] is not None else 0.0,
                }
                for r in rows
            ]

# --------- Пагинация: модели ответа ---------
class CompanyPagedOut(BaseModel):
    items: List[CompanyOut]
    page: int
    page_size: int
    total: int
    pages: int

@router.get("/paged", response_model=CompanyPagedOut)
def list_companies_paged(
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort: str | None = Query("-id", alias='sort')
):
    # 1) Нормализуем параметры
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    # Разрешённые поля сортировки (чтобы не было инъекций)
    allowed_sort = {
        "id": "id",
        "-id": "id DESC",
        "name": "name",
        "-name": "name DESC",
        "industry": "industry",
        "-industry": "industry DESC",
        "region": "region",
        "-region": "region DESC",
    }
    order_by = _order_by_from_sort(sort, allowed_sort, default_sql="id DESC")

    # 2) Собираем WHERE и параметры
    where_sql = ""
    params: list = []
    if q:
        # Ищем по name, industry, region
        where_sql = "WHERE (name ILIKE %s OR industry ILIKE %s OR region ILIKE %s)"
        like = f"%{q}%"
        params.extend([like, like, like])

    # 3) Считаем total
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM company {where_sql}", params)
            total = int(cur.fetchone()[0])

            # 4) Берём страницу данных
            offset = (page - 1) * page_size
            data_sql = (
                "SELECT id, name, industry, region, description "
                f"FROM company {where_sql} "
                f"ORDER BY {order_by} "
                "LIMIT %s OFFSET %s"
            )
            cur.execute(data_sql, params + [page_size, offset])
            rows = cur.fetchall()

    # 5) Считаем кол-во страниц
    pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = [
        {
            "id": r[0],
            "name": r[1],
            "industry": r[2],
            "region": r[3],
            "description": r[4],
        }
        for r in rows
    ]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
    }

# --------- Пагинация рекомендаций: модель ответа ---------
class RecommendationPagedOut(BaseModel):
    items: List[RecommendationCreated]
    page: int
    page_size: int
    total: int
    pages: int

@router.get("/{company_id}/recommendations/paged", response_model=RecommendationPagedOut)
def list_recommendations_paged(
    company_id: int,
    area: Optional[AreaName] = None,
    impact_min: Optional[int] = None,
    impact_max: Optional[int] = None,
    effort_min: Optional[int] = None,
    effort_max: Optional[int] = None,
    sort: str | None = Query("-priority", alias='sort'),
    page: int = 1,
    page_size: int = 20,
):
    # 1) Нормализуем параметры страницы
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    # 2) Белый список сортировок (чтобы не было инъекций)
    allowed_sort = {
        "id": "id",
        "-id": "id DESC",
        "priority": "priority_score",
        "-priority": "priority_score DESC NULLS LAST",
        "impact": "impact",
        "-impact": "impact DESC",
        "effort": "effort",
        "-effort": "effort DESC",
    }
    order_by = _order_by_from_sort(sort, allowed_sort, default_sql="priority_score DESC NULLS LAST, id DESC")

    # 3) WHERE-условия и параметры
    conds = ["company_id = %s"]
    params: list = [company_id]

    if area is not None:
        conds.append("area = %s")
        params.append(area)

    if impact_min is not None:
        conds.append("impact >= %s")
        params.append(impact_min)
    if impact_max is not None:
        conds.append("impact <= %s")
        params.append(impact_max)

    if effort_min is not None:
        conds.append("effort >= %s")
        params.append(effort_min)
    if effort_max is not None:
        conds.append("effort <= %s")
        params.append(effort_max)

    where_sql = "WHERE " + " AND ".join(conds)

    # 4) Считаем общее количество
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM recommendation {where_sql}", params)
            total = int(cur.fetchone()[0])

            # 5) Берём одну страницу данных
            offset = (page - 1) * page_size
            data_sql = (
                "SELECT id, area, title, impact, effort, priority_score "
                f"FROM recommendation {where_sql} "
                f"ORDER BY {order_by} "
                "LIMIT %s OFFSET %s"
            )
            cur.execute(data_sql, params + [page_size, offset])
            rows = cur.fetchall()

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = [
        {
            "id": r[0],
            "area": r[1],
            "title": r[2],
            "impact": r[3],
            "effort": r[4],
            "priority_score": float(r[5]) if r[5] is not None else 0.0,
        }
        for r in rows
    ]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
    }

from fastapi import Response

@router.get("/{company_id}/recommendations/export.csv")
def export_recommendations_csv(
    company_id: int,
    area: Optional[AreaName] = None,
    impact_min: Optional[int] = None,
    impact_max: Optional[int] = None,
    effort_min: Optional[int] = None,
    effort_max: Optional[int] = None,
    q: Optional[str] = None,

    sort: str | None = Query("-priority", alias='sort'),
):
    # белый список сортировок
    allowed_sort = {
        "id": "id",
        "-id": "id DESC",
        "priority": "priority_score",
        "-priority": "priority_score DESC NULLS LAST",
        "impact": "impact",
        "-impact": "impact DESC",
        "effort": "effort",
        "-effort": "effort DESC",
    }
    order_by = _order_by_from_sort(sort, allowed_sort, default_sql="priority_score DESC NULLS LAST, id DESC")

    # собираем WHERE и параметры
    conds = ["company_id = %s"]
    params: list = [company_id]
    if area is not None:
        conds.append("area = %s")
        params.append(area)
    if impact_min is not None:
        conds.append("impact >= %s"); params.append(impact_min)
    if impact_max is not None:
        conds.append("impact <= %s"); params.append(impact_max)
    if effort_min is not None:
        conds.append("effort >= %s"); params.append(effort_min)
    if effort_max is not None:
        conds.append("effort <= %s"); params.append(effort_max)
    where_sql = "WHERE " + " AND ".join(conds)

    # выгружаем все подходящие строки (без пагинации)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, area, title, impact, effort, priority_score "
                f"FROM recommendation {where_sql} "
                f"ORDER BY {order_by}",
                params,
            )
            rows = cur.fetchall()

    # собираем CSV-текст
    # заголовки колонок:
    lines = ["id,area,title,impact,effort,priority_score"]
    for r in rows:
        pid = r[0]
        area_val = r[1] or ""
        title = (r[2] or "").replace('"','""')
        impact = r[3] if r[3] is not None else ""
        effort = r[4] if r[4] is not None else ""
        prio = float(r[5]) if r[5] is not None else 0.0
        # CSV-правило: текстовые поля в кавычках, кавычки внутри удваиваем
        lines.append(f'{pid},{area_val},"{title}",{impact},{effort},{prio}')
    csv_data = "\n".join(lines) + "\n"

    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="recommendations_{company_id}.csv"'
        },
    )

# --------- Утилита: собираем ORDER BY из списка полей по белому списку ---------
from typing import Dict as _Dict  # чтобы не конфликтовало с pydantic Any/Dict

def _order_by_from_sort(sort: str, allowed: _Dict[str, str], default_sql: str) -> str:
    """
    Принимает строку вида "-priority,-impact,name", пропускает только разрешённые ключи
    (из allowed), и склеивает их через запятую. Если ни один не подошёл — возвращает default_sql.
    """
    if not sort:
        return default_sql
    parts = [p.strip() for p in sort.split(",") if p.strip()]
    seq = [allowed[p] for p in parts if p in allowed]
    return ", ".join(seq) if seq else default_sql

# --- autogenerated: generate endpoint ---
from fastapi import Query, Path

@router.post("/{company_id}/recommendations/generate", status_code=201)
def generate_recommendations(
    company_id: int = Path(..., ge=1),
    limit: int = Query(12, ge=1, le=50),
    save: bool = Query(True),
):
    # 1) Сгенерируем список по правилам
    items = generate_default({"id": company_id}, limit=limit)

    saved = 0
    ids_inserted = []

    if save:
        try:
            # Переиспользуем bulk-сохранение из этого же модуля
            res = create_recommendations_bulk(company_id, items, sort=None)  # type: ignore[name-defined]

            # res может быть списком сущностей или словарём с "items"/"data"
            def _extract_ids(seq):
                out = []
                for r in seq or []:
                    if isinstance(r, dict) and "id" in r:
                        out.append(r["id"])
                    else:
                        rid = getattr(r, "id", None)
                        if rid is not None:
                            out.append(rid)
                return out

            if isinstance(res, list):
                saved = len(res)
                ids_inserted = _extract_ids(res)
            elif isinstance(res, dict):
                payload = res.get("items") or res.get("data") or []
                saved = len(payload)
                ids_inserted = _extract_ids(payload)

        except Exception as e:
            # Не падаем, а честно возвращаем, что именно пошло не так
            return {
                "ok": False,
                "company_id": company_id,
                "generated": len(items),
                "saved": 0,
                "ids_inserted": [],
                "error": str(e),
                "items": items,
            }

    return {
        "ok": True,
        "company_id": company_id,
        "generated": len(items),
        "saved": saved,
        "ids_inserted": ids_inserted,
        "items": items,
    }
# --- end autogenerated ---
# --- autogenerated: config weights endpoint ---

@router.get("/config/weights")
def get_config_weights():
    """
    Возвращает актуальные веса моделей (дефолты + переопределения из .env),
    уже с учётом зажимов 0.5..2.0.
    """
    weights = _merge_weights_from_env(DEFAULT_AREA_WEIGHTS)
    return {"ok": True, "weights": weights}
# --- end autogenerated ---
# --- autogenerated: SWOT CRUD ---
from enum import Enum
from typing import List, Optional
from fastapi import Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.analysis import SWOTItem  # таблица swot_items

try:
    from app.db import get_db  # type: ignore
except Exception:
    get_db = None  # type: ignore

class SWOTKind(str, Enum):
    strength = "strength"
    weakness = "weakness"
    opportunity = "opportunity"
    threat = "threat"

class SwotIn(BaseModel):
    kind: SWOTKind
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = None
    impact: Optional[int] = Field(default=None, ge=1, le=5)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    tags: Optional[List[str]] = None

class SwotOut(BaseModel):
    id: int
    company_id: int
    kind: SWOTKind
    title: str
    description: Optional[str] = None
    impact: Optional[int] = None
    confidence: Optional[float] = None
    tags: Optional[List[str]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class SwotPaged(BaseModel):
    total: int
    items: List[SwotOut]

def _db_dep():
    if get_db is None:
        raise HTTPException(status_code=500, detail="DB dependency not configured")
    return Depends(get_db)

def _apply_sort(stmt, sort: str):
    mapping = {"id": SWOTItem.id, "impact": SWOTItem.impact, "created_at": SWOTItem.created_at}
    if not sort:
        return stmt.order_by(SWOTItem.id.desc())
    parts = [p.strip() for p in sort.split(",") if p.strip()]
    order_cols = []
    for p in parts:
        desc = p.startswith("-")
        key = p[1:] if desc else p
        col = mapping.get(key)
        if col is None:
            continue
        order_cols.append(col.desc() if desc else col.asc())
    return stmt.order_by(*(order_cols or [SWOTItem.id.desc()]))

@router.get("/{company_id}/analysis/swot", response_model=SwotPaged)
def list_swot(
    company_id: int,
    kind: Optional[SWOTKind] = Query(None),
    q: Optional[str] = Query(None, description="поиск по заголовку"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("-id"),
    db: Session = _db_dep(),  # type: ignore
):
    base = select(SWOTItem).where(SWOTItem.company_id == company_id)
    if kind:
        base = base.where(SWOTItem.kind == kind.value)
    if q:
        base = base.where(SWOTItem.title.ilike(f"%{q}%"))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    stmt = _apply_sort(base, sort).offset(offset).limit(limit)
    items = db.execute(stmt).scalars().all()
    def to_out(x: SWOTItem) -> SwotOut:
        return SwotOut(
            id=x.id, company_id=x.company_id, kind=SWOTKind(x.kind) if isinstance(x.kind, str) else x.kind,
            title=x.title, description=x.description,
            impact=int(x.impact) if x.impact is not None else None,
            confidence=float(x.confidence) if x.confidence is not None else None,
            tags=list(x.tags) if x.tags is not None else None,
            created_at=str(x.created_at) if x.created_at else None,
            updated_at=str(x.updated_at) if x.updated_at else None,
        )
    return SwotPaged(total=total, items=[to_out(it) for it in items])

@router.post("/{company_id}/analysis/swot", response_model=SwotOut, status_code=status.HTTP_201_CREATED)
def create_swot(company_id: int, payload: SwotIn, db: Session = _db_dep()):  # type: ignore
    row = SWOTItem(
        company_id=company_id, kind=payload.kind.value, title=payload.title,
        description=payload.description, impact=payload.impact,
        confidence=payload.confidence, tags=payload.tags, meta={"source": "api"},
    )
    db.add(row); db.flush(); db.commit(); db.refresh(row)
    return SwotOut(
        id=row.id, company_id=row.company_id, kind=SWOTKind(row.kind), title=row.title,
        description=row.description, impact=row.impact,
        confidence=float(row.confidence) if row.confidence is not None else None,
        tags=row.tags, created_at=str(row.created_at) if row.created_at else None,
        updated_at=str(row.updated_at) if row.updated_at else None
    )

class SwotPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None
    impact: Optional[int] = Field(default=None, ge=1, le=5)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    tags: Optional[List[str]] = None

@router.patch("/{company_id}/analysis/swot/{swot_id}", response_model=SwotOut)
def update_swot(company_id: int, swot_id: int, payload: SwotPatch, db: Session = _db_dep()):  # type: ignore
    row = db.get(SWOTItem, swot_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="SWOT item not found")
    if payload.title is not None: row.title = payload.title
    if payload.description is not None: row.description = payload.description
    if payload.impact is not None: row.impact = payload.impact
    if payload.confidence is not None: row.confidence = payload.confidence
    if payload.tags is not None: row.tags = payload.tags
    db.commit(); db.refresh(row)
    return SwotOut(
        id=row.id, company_id=row.company_id, kind=SWOTKind(row.kind), title=row.title,
        description=row.description, impact=row.impact,
        confidence=float(row.confidence) if row.confidence is not None else None,
        tags=row.tags, created_at=str(row.created_at) if row.created_at else None,
        updated_at=str(row.updated_at) if row.updated_at else None
    )

@router.delete("/{company_id}/analysis/swot/{swot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_swot(company_id: int, swot_id: int, db: Session = _db_dep()):  # type: ignore
    row = db.get(SWOTItem, swot_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="SWOT item not found")
    db.delete(row); db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
# --- end autogenerated ---
