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


def test_menu_contains_core_admin_actions(monkeypatch):
    admin = load_admin_bot(monkeypatch)
    rows = admin.menu_keyboard()["inline_keyboard"]
    callbacks = {button["callback_data"] for row in rows for button in row}
    assert {"stats", "health", "watchlist", "search"} <= callbacks
