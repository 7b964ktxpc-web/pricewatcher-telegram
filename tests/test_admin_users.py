import admin_bot


def test_users_keyboard_contains_user_callbacks():
    keyboard = admin_bot.users_keyboard([{"chat_id": 123, "watchlist_count": 2}])
    assert keyboard["inline_keyboard"][0][0]["callback_data"] == "u:123"


def test_user_items_keyboard_contains_item_callbacks():
    keyboard = admin_bot.user_items_keyboard([{"id": 7, "title": "Футболка"}])
    assert keyboard["inline_keyboard"][0][0]["callback_data"] == "wi:7"
