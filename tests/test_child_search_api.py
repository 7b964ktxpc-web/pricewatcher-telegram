from fastapi.testclient import TestClient

import main


def test_child_search_endpoint(monkeypatch):
    monkeypatch.setattr(main, "child_search", main.child_search)
    monkeypatch.setattr("child_deal_search.search_child_deals", lambda q, limit: {
        "query": {"raw_query": q}, "search_queries": [q], "discovered_count": 1,
        "checked_count": 1, "confirmed_count": 1,
        "deals": [{"lowest_price": 2190, "offer_count": 1}], "unverified": []
    })
    response = TestClient(main.app).get('/api/child-search', params={'q': 'кроссовки мальчику 8 лет до 2500'})
    assert response.status_code == 200
    assert response.json()['confirmed_count'] == 1
