import app.api.companies as companies  # для monkeypatch
HEADERS = {"X-API-Key": "dev", "Content-Type": "application/json"}

def test_generate_preview_ok(api_client):
    r = api_client.post(
        "/companies/1/recommendations/generate",
        params={"limit": 3, "save": "false"},
        headers=HEADERS,
        json={}
    )
    assert r.status_code == 201
    d = r.json()
    assert d["ok"] is True
    assert d["company_id"] == 1
    assert d["generated"] == 3
    assert d["saved"] == 0
    assert d.get("ids_inserted") == []
    assert isinstance(d["items"], list) and len(d["items"]) == 3
    for it in d["items"]:
        for key in ("area", "title", "impact", "effort", "priority_score"):
            assert key in it

def test_generate_save_calls_bulk(api_client, monkeypatch):
    def fake_bulk(company_id, items, sort=None):
        return [{"id": 100 + i, "area": it.get("area"), "title": it.get("title")} for i, it in enumerate(items)]
    monkeypatch.setattr(companies, "create_recommendations_bulk", fake_bulk, raising=False)

    r = api_client.post(
        "/companies/1/recommendations/generate",
        params={"limit": 3, "save": "true"},
        headers=HEADERS,
        json={}
    )
    assert r.status_code == 201
    d = r.json()
    assert d["ok"] is True
    assert d["generated"] == 3
    assert d["saved"] == 3
    assert d["ids_inserted"] == [100, 101, 102]

def test_generate_limit_validation(api_client):
    r = api_client.post(
        "/companies/1/recommendations/generate",
        params={"limit": 0, "save": "false"},
        headers=HEADERS,
        json={}
    )
    assert r.status_code == 422
