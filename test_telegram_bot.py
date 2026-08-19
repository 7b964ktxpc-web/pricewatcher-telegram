from telegram_bot import _looks_like_search, menu_keyboard


def test_search_intent_detection():
    assert _looks_like_search("Найди кроссовки сыну 5 лет до 3000 ₽")
    assert _looks_like_search("А есть дешевле?")


def test_plain_chat_is_not_forced_into_search():
    assert not _looks_like_search("Привет, как у тебя дела?")


def test_menu_has_live_chat_and_search_buttons():
    rows = menu_keyboard()["inline_keyboard"]
    labels = [button["text"] for row in rows for button in row]
    assert "🔎 Найти дешевле" in labels
    assert "💬 Просто поговорить" in labels
    assert "📸 По фото" in labels
