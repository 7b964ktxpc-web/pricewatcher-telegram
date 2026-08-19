from agent_router import expand_queries


def test_expand_queries_is_bounded_and_unique():
    plan = {
        "query": "футболка мальчик 5 лет",
        "category": "футболка",
        "gender": "мальчик",
        "age": 5,
        "size": "110",
        "keywords": ["хлопок", "летняя"],
    }
    queries = expand_queries(plan, "оригинал")
    assert queries[0] == "футболка мальчик 5 лет"
    assert len(queries) <= 3
    assert len(queries) == len(set(queries))


def test_expand_queries_falls_back_to_original():
    queries = expand_queries({"keywords": []}, "детская одежда")
    assert queries == ["детская одежда"]
