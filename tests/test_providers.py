from providers import PROVIDERS, search_sources


def test_provider_registry():
    assert {"wildberries", "ozon", "yandex_market"}.issubset(PROVIDERS)


def test_wb_provider_handles_non_200_without_raising(monkeypatch):
    class Response:
        status_code = 429

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(PROVIDERS["wildberries"], "session", lambda: Session())
    monkeypatch.setattr("providers.RETRIES", 0)
    result = PROVIDERS["wildberries"].search("детская футболка", 5)
    assert result.status == "blocked"
    assert result.items == []


def test_retry_on_429(monkeypatch):
    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

        def json(self):
            return {"data": {"products": []}}

    class Session:
        def __init__(self):
            self.calls = 0

        def get(self, *args, **kwargs):
            self.calls += 1
            return Response(429 if self.calls == 1 else 200)

    session = Session()
    provider = PROVIDERS["wildberries"]
    monkeypatch.setattr(provider, "session", lambda: session)
    monkeypatch.setattr("providers.RETRIES", 1)
    monkeypatch.setattr("providers.BACKOFF", 0)
    result = provider.search("детская футболка", 5)
    assert result.status == "ok"
    assert session.calls == 2


def test_search_sources_deduplicates_and_sorts(monkeypatch):
    class FakeProvider:
        def search(self, query, limit):
            return type("Result", (), {
                "source": "fake",
                "marketplace": "fake",
                "status": "ok",
                "items": [
                    {"marketplace": "fake", "product_id": "2", "price": 500},
                    {"marketplace": "fake", "product_id": "1", "price": 300},
                    {"marketplace": "fake", "product_id": "1", "price": 300},
                ],
                "error": None,
            })()

    monkeypatch.setitem(PROVIDERS, "fake", FakeProvider())
    result = search_sources("футболка", 10, ["fake"])
    assert result["count"] == 2
    assert [x["price"] for x in result["items"]] == [300, 500]
