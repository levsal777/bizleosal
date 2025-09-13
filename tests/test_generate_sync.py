import asyncio
from unittest.mock import MagicMock, patch

from backend.app.schemas.recommendations import AiCompleteResponse, RecItem, Meta

HEADERS = {"X-API-Key": "dev", "Content-Type": "application/json"}
COMPANY_ID = 1

@patch("backend.app.api.companies.asyncio.run")
@patch("backend.app.api.companies.get_conn")
def test_generate_recommendations_ok(mock_get_conn, mock_asyncio_run, api_client):
    # --- Arrange ---
    # Mock DB
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 2
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    # Mock asyncio.run
    items = [
        RecItem(
            id=f"rec_{i}",
            area="overall",
            title=f"Recommendation {i}",
            rationale="Because it is good",
            steps=["step 1"],
            impact=4,
            effort=2,
            priority=80.0,
        )
        for i in range(2)
    ]
    ai_response = AiCompleteResponse(items=items, meta=Meta())
    mock_asyncio_run.return_value = ai_response

    # --- Act ---
    r = api_client.post(
        f"/companies/{COMPANY_ID}/recommendations/generate",
        headers=HEADERS,
        json={
            "company": {"name": "Test Inc.", "industry": "tech"},
            "goals": ["increase revenue"],
        },
    )

    # --- Assert ---
    assert r.status_code == 200
    data = r.json()
    assert data["inserted"] == 2
    assert data["requested"] == 2
    assert data["company_id"] == COMPANY_ID

    # Check that asyncio.run was called
    mock_asyncio_run.assert_called_once()

    # Check that the DB was called correctly
    mock_get_conn.assert_called_once()
    mock_cursor.executemany.assert_called_once()

    # Check the data passed to executemany
    args, _ = mock_cursor.executemany.call_args
    sql = args[0]
    params = args[1]

    assert "INSERT INTO recommendation" in sql
    assert len(params) == 2
    assert params[0] == (COMPANY_ID, "overall", "Recommendation 0", 4, 2, 80.0)
    assert params[1] == (COMPANY_ID, "overall", "Recommendation 1", 4, 2, 80.0)

def test_generate_recommendations_invalid_payload(api_client):
    # --- Act ---
    r = api_client.post(
        f"/companies/{COMPANY_ID}/recommendations/generate",
        headers=HEADERS,
        json={
            "company": {"name": "Test Inc."},
            "limit": "not-an-int" # Invalid limit
        },
    )

    # --- Assert ---
    assert r.status_code == 400
    assert "Invalid payload" in r.json()["detail"]
