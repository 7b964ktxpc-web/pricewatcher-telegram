from __future__ import annotations

import watchlist_checker


def test_price_uses_lowest_price() -> None:
    assert watchlist_checker._price({"price": 1299}) == 1299.0
    assert watchlist_checker._price({"lowest_price": 999}) == 999.0
    assert watchlist_checker._price({"price": "999"}) is None


def test_best_price_prefers_exact_watched_url() -> None:
    item = {"url": "https://example.test/p/1"}
    offers = [
        {"url": "https://example.test/p/other", "price": 100},
        {"url": "https://example.test/p/1", "price": 4500},
        {"url": "https://example.test/p/1", "price": 4300},
    ]
    assert watchlist_checker._best_price(item, offers) == 4300.0


def test_best_price_falls_back_to_search_results() -> None:
    item = {"url": "https://example.test/p/missing"}
    offers = [{"url": "https://example.test/p/1", "price": 1400}, {"price": 1200}]
    assert watchlist_checker._best_price(item, offers) == 1200.0


def test_check_once_updates_price_and_notifies_on_drop(monkeypatch) -> None:
    items = [
        {
            "chat_id": 42,
            "item_key": "https://example.test/p/1",
            "title": "Детские кроссовки",
            "url": "https://example.test/p/1",
            "last_price": 5000,
        }
    ]
    sent: list[tuple[int, str]] = []
    updates: list[tuple[int, str, float]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"confirmed": [{"url": "https://example.test/p/other", "price": 1000}, {"url": "https://example.test/p/1", "price": 4200}]}

    monkeypatch.setattr(watchlist_checker, "list_all", lambda: items)
    monkeypatch.setattr(watchlist_checker.requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(watchlist_checker, "update_price", lambda chat_id, item_key, price: updates.append((chat_id, item_key, price)))
    monkeypatch.setattr(watchlist_checker, "send_message", lambda chat_id, text, **kwargs: sent.append((chat_id, text)))

    assert watchlist_checker.check_once() == 1
    assert updates == [(42, "https://example.test/p/1", 4200.0)]
    assert len(sent) == 1
    assert "Цена снизилась" in sent[0][1]
    assert "800" in sent[0][1]


def test_check_once_does_not_notify_when_price_is_unchanged(monkeypatch) -> None:
    items = [{"chat_id": 7, "item_key": "item-7", "title": "Куртка", "url": "https://example.test/p/7", "last_price": 3000}]
    sent: list[str] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"items": [{"url": "https://example.test/p/7", "price": 3000}, {"price": 2000}]}

    monkeypatch.setattr(watchlist_checker, "list_all", lambda: items)
    monkeypatch.setattr(watchlist_checker.requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(watchlist_checker, "update_price", lambda *args: None)
    monkeypatch.setattr(watchlist_checker, "send_message", lambda chat_id, text, **kwargs: sent.append(text))

    assert watchlist_checker.check_once() == 1
    assert sent == []


def test_check_once_ignores_items_without_numeric_price(monkeypatch) -> None:
    items = [{"chat_id": 1, "item_key": "x", "title": "Товар", "last_price": 1000}]

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"confirmed": [{"price": "неизвестно"}]}

    monkeypatch.setattr(watchlist_checker, "list_all", lambda: items)
    monkeypatch.setattr(watchlist_checker.requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(watchlist_checker, "update_price", lambda *args: (_ for _ in ()).throw(AssertionError("should not update")))
    monkeypatch.setattr(watchlist_checker, "send_message", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not notify")))

    assert watchlist_checker.check_once() == 0
