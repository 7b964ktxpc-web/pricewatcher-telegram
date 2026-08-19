from provider_engine import _dedupe, _matches


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
