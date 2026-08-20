from provider_engine import _dedupe, _matches
from resilient_provider_engine import search_sources


def test_query_matches_multiple_product_fields():
    item = {"title": "Футболка", "category": "Одежда для мальчиков", "brand": "Acme", "description": "Хлопок"}
    assert _matches(item, "футболка мальчиков")


def test_dedupe_prefers_cheaper_items():
    items = [
        {"marketplace": "ozon", "id": "1", "price": 1200, "discount_percent": 10},
        {"marketplace": "ozon", "id": "1", "price": 900, "discount_percent": 20},
        {"marketplace": "wb", "id": "2", "price": 1000, "discount_percent": 5},
    ]
    result = _dedupe(items, 10)
    assert len(result) == 2
    assert result[0]["price"] == 1000 or result[0]["price"] == 900
    assert {x["id"] for x in result} == {"1", "2"}


def test_default_search_includes_feed_adapters(monkeypatch):
    calls = []

    def fake_run_source(source, query, limit):
        calls.append(source)
        return {"source": source, "status": "not_configured", "items": [], "error": "test"}

    monkeypatch.setattr("resilient_provider_engine._run_source", fake_run_source)
    result = search_sources("футболка", 5)

    assert "wildberries_feed" in calls
    assert "ozon_feed" in calls
    assert "yandex_market_feed" not in calls
    assert "simaland_feed" in calls
    assert result["ready"] is False
