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


def test_unknown_source():
    response = client.get("/api/search", params={"q": "футболка", "source": "does-not-exist"})
    assert response.status_code == 400
