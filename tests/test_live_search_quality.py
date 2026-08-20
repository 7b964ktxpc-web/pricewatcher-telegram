from live_search_agent import search_live


def test_sparse_results_trigger_bounded_second_search(monkeypatch):
    monkeypatch.setattr(
        "live_search_agent.build_plan",
        lambda query: {"query": query, "category": "кроссовки", "age": "6", "gender": "мальчик", "size": "30", "max_price": 2500},
    )
    monkeypatch.setattr("live_search_agent.expand_queries", lambda plan, original: [original])
    calls = []

    def fake_fetch(path, query, limit):
        calls.append((path, query))
        if len(calls) <= 2:
            return path, {"items": [{"id": "one", "title": "Кроссовки", "price": 2400}]}, None
        return path, {"items": [{"id": "two", "title": "Кроссовки Nike", "price": 2300}]}, None

    monkeypatch.setattr("live_search_agent._fetch", fake_fetch)
    result = search_live("кроссовки мальчику 6 лет размер 30 до 2500", limit=8)

    assert result["fallback_used"] is True
    assert result["fallback_reason"] == "sparse"
    assert len(result["items"]) == 2
    assert "мальчик" in result["fallback_query"]
    assert "30" in result["fallback_query"]
    assert "2500" not in result["fallback_query"]


def test_sparse_results_without_price_do_not_relax_constraints(monkeypatch):
    monkeypatch.setattr(
        "live_search_agent.build_plan",
        lambda query: {"query": query, "category": "куртка", "age": "7", "gender": "девочка", "size": "128"},
    )
    monkeypatch.setattr("live_search_agent.expand_queries", lambda plan, original: [original])
    calls = []
    monkeypatch.setattr(
        "live_search_agent._fetch",
        lambda path, query, limit: (calls.append((path, query)) or (path, {"items": [{"id": "one", "title": "Куртка", "price": 2000}]}, None)),
    )

    result = search_live("куртка девочке 7 лет размер 128", limit=8)

    assert result["fallback_used"] is False
    assert result["fallback_query"] is None
    assert len(calls) == 2
