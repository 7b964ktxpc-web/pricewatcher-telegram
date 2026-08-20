"""Regression checks for Telegram photo/callback handling."""

from telegram_bot_runner import _handle_photo, _handle_update


def test_photo_caption_is_used_as_search_query(monkeypatch):
    searched = []
    monkeypatch.setattr("telegram_bot_runner._download_telegram_file", lambda file_id: (b"image", "image/jpeg"))
    monkeypatch.setattr("telegram_bot_runner.bot.describe_image", lambda image, mime: {"query": "vision query"})
    monkeypatch.setattr("telegram_bot_runner.bot._remember", lambda *args: None)
    monkeypatch.setattr("telegram_bot_runner.bot.send_message", lambda *args, **kwargs: None)
    monkeypatch.setattr("telegram_bot_runner.bot._search", lambda chat_id, query: searched.append((chat_id, query)))
    _handle_photo(1, [{"file_id": "p1", "file_size": 10}], "кроссовки мальчик 35")
    assert searched == [(1, "кроссовки мальчик 35")]


def test_callback_failure_does_not_escape(monkeypatch):
    monkeypatch.setattr("telegram_bot_runner.bot._handle_callback", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("callback failure")))
    _handle_update({"callback_query": {"id": "cb1", "message": {"chat": {"id": 1}}, "data": "search"}})
