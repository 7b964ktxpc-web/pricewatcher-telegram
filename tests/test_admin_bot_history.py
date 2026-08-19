from admin_bot import _format_history


def test_format_history_shows_chain_and_change():
    history = [
        {"price": 4990, "recorded_at": "2026-08-18 10:00:00"},
        {"price": 4490, "recorded_at": "2026-08-19 10:00:00"},
        {"price": 3990, "recorded_at": "2026-08-20 10:00:00"},
    ]
    text = _format_history(history)
    assert "4 990 ₽ → 4 490 ₽ → 3 990 ₽" in text
    assert "-11.1%" in text


def test_format_history_handles_empty():
    assert _format_history([]) == "📉 История: нет данных"
