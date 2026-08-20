from telegram_bot import _search


def test_follow_up_search_uses_resolved_query_and_calls_live_agent(monkeypatch):
    sent = []
    searched = []

    monkeypatch.setattr("telegram_bot._typing", lambda chat_id: None)
    monkeypatch.setattr("telegram_bot.send_message", lambda chat_id, text, markup=None: sent.append(text))
    monkeypatch.setattr("telegram_bot._last_results", {})
    monkeypatch.setattr(
        "telegram_bot.search_live",
        lambda query, limit=8: searched.append(query) or {"items": [{"title": "Синий товар", "price": 1990}]},
    )

    _search(42, "кроссовки мальчику 6 лет размер 30. Уточнение пользователя: другого цвета")

    assert searched == ["кроссовки мальчику 6 лет размер 30. Уточнение пользователя: другого цвета"]
    assert any("Нашла один вариант" in text for text in sent)
