from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_sources():
    response = client.get("/api/sources")
    assert response.status_code == 200
    sources = response.json()["sources"]
    assert "wildberries" in sources
    assert "ozon" in sources
    assert "yandex_market" in sources
    assert "simaland" in sources


def test_test_product():
    response = client.get("/api/test-product")
    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == "123"
    assert body["price"] == 999.0


def test_connections_does_not_expose_credentials():
    response = client.get("/api/connections")
    assert response.status_code == 200
    body = response.json()
    assert "ai" in body
    assert "telegram" in body
    assert "marketplace_apis" in body
    assert "api_key" not in str(body).lower()
    assert "token" not in str(body).lower() or "token_configured" in str(body).lower()


def test_readiness():
    response = client.get("/api/readiness")
    assert response.status_code == 200
    body = response.json()
    assert "ready" in body
    assert "telegram" in body
    assert "ai" in body
    assert "marketplaces" in body
    assert "feeds" in body


def test_unknown_source():
    response = client.get("/api/search", params={"q": "футболка", "source": "does-not-exist"})
    assert response.status_code == 400
