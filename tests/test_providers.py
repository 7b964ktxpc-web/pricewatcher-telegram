from providers import PROVIDERS


def test_provider_registry():
    assert {"wildberries", "ozon", "yandex_market"}.issubset(PROVIDERS)


def test_wb_provider_handles_non_200_without_raising(monkeypatch):
    class Response:
        status_code = 429

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(PROVIDERS["wildberries"], "session", lambda: Session())
    result = PROVIDERS["wildberries"].search("детская футболка", 5)
    assert result.status == "blocked"
    assert result.items == []
