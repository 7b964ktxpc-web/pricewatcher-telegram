from live_search_agent import _fallback_query


def test_fallback_preserves_product_constraints_when_relaxing_price():
    plan = {
        "query": "кроссовки мальчик 6 лет",
        "category": "кроссовки",
        "age": 6,
        "gender": "мальчик",
        "size": "30",
        "color": "синие",
        "brand": "Nike",
        "max_price": 2500,
        "keywords": ["кроссовки"],
    }

    query = _fallback_query("кроссовки мальчику 6 лет размер 30 синие Nike до 2500", plan)

    assert query is not None
    assert "кроссовки" in query
    assert "6" in query
    assert "мальчик" in query
    assert "30" in query
    assert "синие" in query
    assert "Nike" in query
    assert "2500" not in query


def test_fallback_does_not_relax_constraints_without_price():
    plan = {
        "query": "кроссовки мальчик 6 лет",
        "category": "кроссовки",
        "age": 6,
        "gender": "мальчик",
        "size": "30",
    }

    assert _fallback_query("кроссовки мальчику 6 лет размер 30", plan) is None
