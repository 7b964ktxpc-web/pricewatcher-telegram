"""Regression checks for Telegram photo/callback handling."""

from telegram_bot_runner import _handle_update


def test_photo_caption_is_used(monkeypatch):
    calls = []
    monkeypatch.setattr("telegram_bot_runner._handle_photo", lambda chat_id, photos: calls.append((chat_id, photos)))
    _handle_update({"message": {"chat": {"id": 1}, "photo": [{"file_id": "p1"}], "caption": "кроссовки мальчик 35"}})
    assert calls == [(1, [{"file_id": "p1"}])]


def test_callback_error_does_not_escape(monkeypatch):
    monkeypatch.setattr("telegram_bot_runner.bot._api", lambda *args, **kwargs: {"ok": True})
    def fail(*args, **kwargs):
        raise RuntimeError("callback failure")
    monkeypatch.setattr("telegram_bot_runner.bot._handle_callback", fail)
    try:
        _handle_update({"callback_query": {"id": "cb1", "message": {"chat": {"id": 1}}, "data": "search"}})
    except RuntimeError:
        assert False, "callback exception escaped update handler"
