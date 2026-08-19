import admin_bot
from admin_users import card, search_text


def test_users_keyboard_contains_user_callbacks():
    keyboard = admin_bot.users_keyboard([{"chat_id": 123, "watchlist_count": 2}])
    assert keyboard["inline_keyboard"][0][0]["callback_data"] == "u:123"


def test_user_items_keyboard_contains_item_callbacks():
    keyboard = admin_bot.user_items_keyboard([{"id": 7, "title": "Футболка"}])
    assert keyboard["inline_keyboard"][0][0]["callback_data"] == "wi:7"


def test_search_text_empty_result(monkeypatch):
    monkeypatch.setattr("admin_users.find", lambda query, limit=20: [])
    assert "не найден" in search_text("12345")


def test_card_formats_user(monkeypatch):
    monkeypatch.setattr(
        "admin_users.find",
        lambda query, limit=20: [{"chat_id": 12345, "watchlist_count": 3, "last_activity": "2026-08-20 10:00:00"}],
    )
    text = card(12345)
    assert "12345" in text
    assert "Watchlist: 3" in text
