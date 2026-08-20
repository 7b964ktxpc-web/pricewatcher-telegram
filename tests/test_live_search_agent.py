from live_search_agent import search_live


def test_live_search_expands_queries_and_merges_duplicates(monkeypatch):
    monkeypatch.setattr(
        "live_search_agent.build_plan",
        lambda query: {"query": query, "category": "кроссовки", "keywords": ["детские"]},
    )
    monkeypatch.setattr(
        "live_search_agent.expand_queries",
        lambda plan, original: [original, "кроссовки детские"],
    )
    calls = []

    def fake_fetch(path, query, limit):
        calls.append((path, query, limit))
        return path, {"items": [{"id": "same", "title": "Кроссовки", "price": 2500, "url": "https://example.test/1"}]}, None

    monkeypatch.setattr("live_search_agent._fetch", fake_fetch)
    result = search_live("кроссовки мальчику 5 лет", limit=8)

    assert len(calls) == 4
    assert len(result["items"]) == 1
    assert result["items"][0]["price"] == 2500
    assert result["live"] is True


def test_live_search_does_not_require_preloaded_catalog(monkeypatch):
    monkeypatch.setattr(
        "live_search_agent.build_plan",
        lambda query: {"query": query, "keywords": []},
    )
    monkeypatch.setattr("live_search_agent.expand_queries", lambda plan, original: [original])
    monkeypatch.setattr(
        "live_search_agent._fetch",
        lambda path, query, limit: (path, {"items": [{"title": "Найденный товар", "price": 1990}]}, None),
    )
    result = search_live("рюкзак школьный", limit=8)
    assert result["items"][0]["title"] == "Найденный товар"
