import os, contextlib
DATABASE_URL = os.getenv("DATABASE_URL")  # пример: postgresql://myapp:supersecret@db:5432/myapp

try:
    from psycopg_pool import ConnectionPool
    _pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=5, open=True)

    @contextlib.contextmanager
    def get_conn():
        with _pool.connection() as conn:
            yield conn
except Exception:
    import psycopg
    @contextlib.contextmanager
    def get_conn():
        with psycopg.connect(DATABASE_URL) as conn:
            yield conn
