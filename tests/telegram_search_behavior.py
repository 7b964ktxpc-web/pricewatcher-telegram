"""Telegram search behavior regression checks."""

from telegram_bot import _extract_search_items


def test_empty_search_response_is_not_treated_as_server_failure():
    assert _extract_search_items({"ready": True, "count": 0, "items": []}) == []


def test_confirmed_items_are_supported():
    items = _extract_search_items({"confirmed": [{"title": "Куртка", "price": 2990}]})
    assert len(items) == 1
    assert items[0]["title"] == "Куртка"
