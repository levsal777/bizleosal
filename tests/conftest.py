import pytest
from starlette.testclient import TestClient
import os

os.environ["API_KEY"] = "dev"
os.environ["DATABASE_URL"] = "postgresql://test:test@test/test"

from backend.app.main import app

@pytest.fixture
def api_client():
    with TestClient(app) as client:
        yield client
