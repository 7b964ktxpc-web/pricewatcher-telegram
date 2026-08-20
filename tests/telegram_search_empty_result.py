"""Regression coverage for a healthy search API returning zero products."""

from telegram_bot import _extract_search_items


def test_ready_zero_count_is_a_valid_empty_result():
    assert _extract_search_items({"ready": True, "count": 0, "items": []}) == []


def test_confirmed_items_are_supported():
    assert _extract_search_items({"ready": True, "confirmed": [{"title": "Кроссовки"}]}) == [{"title": "Кроссовки"}]
