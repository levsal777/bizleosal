import pytest
from starlette.testclient import TestClient

try:
    from app.main import app  # если есть полноценный app
except Exception:
    from fastapi import FastAPI
    from app.api.companies import router
    app = FastAPI()
    app.include_router(router)

@pytest.fixture
def api_client():
    with TestClient(app) as client:
        yield client
