from app.api.companies import router as companies_router
# /srv/apps/myapp/backend/app/main.py
# Biz Analytics API — главный файл приложения

import os
import json
import logging
from time import perf_counter_ns
from uuid import uuid4

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes.ai import router as ai_router
from app.schemas.recommendations import ErrorResponse

# --- psycopg3 для /readyz ---
try:
    import psycopg  # psycopg3
except Exception:
    psycopg = None  # обработаем аккуратно ниже

# --- Prometheus метрики ---
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
    PROM_ENABLED = True
except Exception:
    # если зависимости нет — эндпоинт /metrics вернёт 503
    PROM_ENABLED = False

# ========= ЛОГИ (JSON-строка на событие) =========
def _configure_logger() -> logging.Logger:
    logger = logging.getLogger("bizapp")
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    logging.getLogger().setLevel(logging.WARNING)
    return logger

LOGGER = _configure_logger()

def _log_json(event: str, **fields) -> None:
    try:
        LOGGER.info(json.dumps({"event": event, **fields}, ensure_ascii=False))
    except Exception:
        LOGGER.warning('{"event":"log_error","detail":"failed_to_json_dump"}')

# ========= ВСПОМОГАТЕЛЬНОЕ =========
def _client_ip(request: Request) -> str:
    xfwd = request.headers.get("x-forwarded-for")
    if xfwd:
        return xfwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _build_dsn() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "postgres")
    pwd  = os.getenv("POSTGRES_PASSWORD", "postgres")
    db   = os.getenv("POSTGRES_DB", "postgres")
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

# ========= Prometheus счетчики/гистограммы =========
if PROM_ENABLED:
    HTTP_REQUESTS_TOTAL = Counter(
        "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
    )
    HTTP_REQUEST_DURATION = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path", "status"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    )

# ========= Приложение =========
app = FastAPI(
    title="Biz Analytics API",
    version="1.0.0",
    servers=[{"url": "https://api.bizleosal.ru"}],
)


# --- API Key guard for /companies and /v1/companies ---
API_KEY = os.getenv("API_KEY")

@app.middleware("http")
async def require_api_key_for_companies(request: Request, call_next):
    path = request.url.path
    if path.startswith("/companies") or path.startswith("/v1/companies"):
        if not API_KEY:
            return JSONResponse({"detail": "server_misconfigured: API_KEY not set"}, status_code=500)
        if request.headers.get("x-api-key") != API_KEY:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)
# --- end guard ---

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://bizleosal.ru",
        "https://www.bizleosal.ru",
        "http://localhost:3000",
        "http://localhost:5173",
        "https://app.bizleosal.ru",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Trace-Id"],
    max_age=86400,
)

# --- TraceId middleware ---
class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Request-Id") or str(uuid4())
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

# --- Access log + метрики ---
class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = perf_counter_ns()
        trace_id = getattr(request.state, "trace_id", str(uuid4()))
        ip = _client_ip(request)
        ua = request.headers.get("user-agent", "-")
        method = request.method
        path = request.url.path
        status = 500
        try:
            response: Response = await call_next(request)
            status = response.status_code
            return response
        finally:
            dur_ms = round((perf_counter_ns() - t0) / 1_000_000, 1)
            _log_json(
                "http_request",
                method=method, path=path, status=status,
                duration_ms=dur_ms, trace_id=trace_id, ip=ip, ua=ua,
            )
            if PROM_ENABLED:
                try:
                    dur_s = dur_ms / 1000.0
                    HTTP_REQUESTS_TOTAL.labels(method, path, str(status)).inc()
                    HTTP_REQUEST_DURATION.labels(method, path, str(status)).observe(dur_s)
                except Exception:
                    pass  # метрики не должны ломать запрос

app.add_middleware(TraceIdMiddleware)
app.add_middleware(AccessLogMiddleware)

# --- Глобальный перехват неожиданных ошибок ---
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", str(uuid4()))
    _log_json("unhandled_exception", trace_id=trace_id, path=request.url.path, detail=str(exc.__class__.__name__))
    payload = ErrorResponse(title="Internal Server Error", status=500, detail="Unexpected error", trace_id=trace_id)
    return JSONResponse(status_code=500, content=payload.dict())

# --- Бизнес-роуты ---
app.include_router(ai_router)
app.include_router(companies_router)  # без prefix здесь, т.к. в companies.py уже prefix="/companies"

# --- Healthz (GET/HEAD) ---
@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.head("/healthz")
def healthz_head():
    return Response(status_code=200)

# --- Readyz: пингуем Postgres (SELECT 1) ---
@app.get("/readyz")
def readyz():
    if psycopg is None:
        raise HTTPException(status_code=503, detail="psycopg not installed")
    dsn = _build_dsn()
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"db_not_ready: {e.__class__.__name__}")

# --- /metrics: Prometheus ---
@app.get("/metrics")
def metrics():
    if not PROM_ENABLED:
        raise HTTPException(status_code=503, detail="prometheus_client not installed")
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

# --- Корневой пинг ---
@app.get("/")
def root():
    return {"status": "ok"}

