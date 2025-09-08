from __future__ import annotations
import os
from contextlib import contextmanager

# Попытка импортировать «родные» функции проекта, если они есть
_get_conn = None
try:
    from app.core.db import get_conn as _get_conn  # type: ignore
except Exception:
    _get_conn = None

def _dsn_from_env() -> str:
    # 1) Прямой DSN
    for key in ("DATABASE_URL", "DB_DSN", "POSTGRES_DSN"):
        v = os.getenv(key)
        if v:
            return v
    # 2) Соберём DSN из кусков
    user = os.getenv("POSTGRES_USER") or os.getenv("DB_USER") or "postgres"
    pwd  = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD") or ""
    host = os.getenv("POSTGRES_HOST") or "myapp-db"
    port = os.getenv("POSTGRES_PORT") or "5432"
    db   = os.getenv("POSTGRES_DB") or os.getenv("DB_NAME") or "postgres"
    if pwd:
        return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
    return f"postgresql://{user}@{host}:{port}/{db}"

@contextmanager
def get_conn():
    """
    Унифицированный контекст: with get_conn() as conn: ...
    Если есть «родной» get_conn — делегируем ему.
    Иначе подключаемся через psycopg2 по DSN из окружения.
    """
    if _get_conn is not None:
        with _get_conn() as c:  # делегирование в проектную функцию
            yield c
        return

    dsn = _dsn_from_env()
    try:
        import psycopg2  # type: ignore
    except Exception as e:
        raise RuntimeError("psycopg2 не установлен в образе backend. Установи его в requirements.") from e

    conn = psycopg2.connect(dsn)
    try:
        yield conn
    finally:
        conn.close()

def get_db():
    """
    Совместимость для Depends(get_db): yield соединение.
    """
    with get_conn() as conn:
        yield conn
