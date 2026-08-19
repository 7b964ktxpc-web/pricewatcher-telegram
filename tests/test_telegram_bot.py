from telegram_bot import _looks_like_search, deal_keyboard, menu_keyboard
from telegram_photo_search import _extract


def test_search_intent_detects_natural_product_request():
    assert _looks_like_search("Нужны кроссовки сыну 5 лет до 3000 рублей") is True


def test_search_intent_does_not_force_normal_chat_into_search():
    assert _looks_like_search("Как у тебя дела?") is False


def test_menu_has_live_conversation_and_search_buttons():
    keyboard = menu_keyboard()["inline_keyboard"]
    labels = [button["text"] for row in keyboard for button in row]
    assert "🔎 Найти дешевле" in labels
    assert "💬 Просто поговорить" in labels
    assert "📸 По фото" in labels


def test_deal_keyboard_has_buy_cheaper_refresh_and_watch_actions():
    keyboard = deal_keyboard({"url": "https://example.com/item"}, 0)["inline_keyboard"]
    labels = [button["text"] for row in keyboard for button in row]
    assert "🛒 Купить" in labels
    assert "💰 Найти дешевле" in labels
    assert "🔄 Проверить" in labels
    assert "🔔 Следить" in labels
    assert keyboard[0][0]["url"] == "https://example.com/item"


def test_photo_description_extracts_structured_query():
    result = _extract('{"query":"красные детские кроссовки","color":"красный","size":"30","keywords":["кроссовки"]}')
    assert result["query"] == "красные детские кроссовки"
    assert result["color"] == "красный"
    assert result["size"] == "30"


def test_photo_description_falls_back_to_text():
    result = _extract("детская синяя куртка")
    assert result["query"] == "детская синяя куртка"
    assert result["keywords"] == []
