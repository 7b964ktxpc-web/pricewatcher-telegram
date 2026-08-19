from ai_agent import _fallback_plan, _json_object


def test_json_object_handles_fenced_json():
    assert _json_object('```json\n{"query":"футболка","limit":10}\n```') == {
        "query": "футболка",
        "limit": 10,
    }


def test_fallback_extracts_price_age_gender():
    plan = _fallback_plan("футболка мальчик 5 лет до 1000 рублей")
    assert plan["age"] == 5
    assert plan["gender"] == "мальчик"
    assert plan["max_price"] == 1000
    assert plan["limit"] == 20
