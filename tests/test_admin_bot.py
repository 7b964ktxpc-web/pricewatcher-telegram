import importlib


def load_admin_bot(monkeypatch):
    monkeypatch.setenv("ADMIN_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ADMIN_USER_IDS", "123,456")
    import admin_bot
    return importlib.reload(admin_bot)


def test_is_admin_allows_only_configured_ids(monkeypatch):
    admin = load_admin_bot(monkeypatch)
    assert admin.is_admin(123)
    assert admin.is_admin(456)
    assert not admin.is_admin(999)
    assert not admin.is_admin(None)


def test_disabled_without_token_or_admin_ids(monkeypatch):
    monkeypatch.delenv("ADMIN_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    import admin_bot
    admin = importlib.reload(admin_bot)
    assert not admin.enabled()


def test_menu_contains_all_admin_actions(monkeypatch):
    admin = load_admin_bot(monkeypatch)
    rows = admin.menu_keyboard()["inline_keyboard"]
    callbacks = {button["callback_data"] for row in rows for button in row}
    assert {"stats", "health", "users", "watchlist", "search", "sources", "broadcast", "menu"} <= callbacks


def test_text_handlers_route_commands(monkeypatch):
    admin = load_admin_bot(monkeypatch)
    sent = []
    monkeypatch.setattr(admin, "send_message", lambda chat_id, text, reply_markup=None: sent.append((chat_id, text)))
    admin.handle_text(10, 123, "/stats")
    admin.handle_text(10, 123, "/health")
    admin.handle_text(10, 123, "/users")
    admin.handle_text(10, 123, "/watchlist")
    admin.handle_text(10, 123, "/search")
    admin.handle_text(10, 123, "/sources")
    assert len(sent) == 6


def test_non_admin_cannot_trigger_commands(monkeypatch):
    admin = load_admin_bot(monkeypatch)
    sent = []
    monkeypatch.setattr(admin, "send_message", lambda *args, **kwargs: sent.append(args))
    admin.handle_text(10, 999, "/stats")
    assert sent == []
