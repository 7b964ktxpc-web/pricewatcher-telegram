import admin_notifications


def test_format_notification_shows_prices_and_discount():
    text = admin_notifications.format_notification({
        "title": "Куртка",
        "chat_id": 123,
        "previous_price": 5000,
        "price": 3990,
        "drop_amount": 1010,
        "drop_percent": 20.2,
        "source": "Ozon",
        "url": "https://example.com/item",
    })
    assert "5 000 ₽ → 3 990 ₽" in text
    assert "1 010 ₽" in text
    assert "20.2%" in text


def test_list_notifications_filters_by_amount_and_percent(monkeypatch):
    class Cursor:
        def fetchall(self):
            return [
                {"event_key": "a", "chat_id": 1, "item_key": "a", "price": 4000, "notified_at": 1, "title": "A", "url": "u", "source": "s", "previous_price": 5000},
                {"event_key": "b", "chat_id": 2, "item_key": "b", "price": 4900, "notified_at": 2, "title": "B", "url": "u", "source": "s", "previous_price": 5000},
            ]

    class Conn:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, *args):
            return Cursor()

    monkeypatch.setattr(admin_notifications, "init_db", lambda: None)
    monkeypatch.setattr(admin_notifications.sqlite3, "connect", lambda *args, **kwargs: Conn())
    rows = admin_notifications.list_notifications(min_drop_amount=500, min_drop_percent=10)
    assert len(rows) == 1
    assert rows[0]["event_key"] == "a"
