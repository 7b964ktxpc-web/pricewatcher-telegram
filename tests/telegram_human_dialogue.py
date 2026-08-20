from telegram_bot import _handle_callback


def test_search_error_is_human_friendly(monkeypatch):
    sent = []
    monkeypatch.setattr("telegram_bot._typing", lambda chat_id: None)
    monkeypatch.setattr("telegram_bot.search_live", lambda query, limit=8: (_ for _ in ()).throw(RuntimeError("network")))
    monkeypatch.setattr("telegram_bot.send_message", lambda chat_id, text, markup=None: sent.append(text))
    from telegram_bot import _search
    _search(1, "кроссовки мальчику 5 лет")
    assert "API" not in sent[0]
    assert "network" not in sent[0]
    assert "поиск" in sent[0].lower()


def test_search_results_use_natural_intro(monkeypatch):
    sent = []
    monkeypatch.setattr("telegram_bot._typing", lambda chat_id: None)
    monkeypatch.setattr("telegram_bot.search_live", lambda query, limit=8: {"items": [{"title": "Кроссовки", "price": 1990, "source": "магазин"}]})
    monkeypatch.setattr("telegram_bot.send_message", lambda chat_id, text, markup=None: sent.append(text))
    from telegram_bot import _search
    _search(1, "кроссовки мальчику 5 лет")
    assert any("Нашла один вариант" in text for text in sent)
    assert any("API" not in text for text in sent)
