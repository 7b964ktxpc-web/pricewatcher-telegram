import importlib


def test_verify_uses_price_verifier(monkeypatch, tmp_path):
    db = tmp_path / "watchlist.sqlite3"
    import watchlist_store
    monkeypatch.setattr(watchlist_store, "DB_PATH", str(db))
    import admin_watchlist
    monkeypatch.setattr(admin_watchlist, "DB_PATH", str(db))
    importlib.reload(admin_watchlist)
    with __import__("sqlite3").connect(db) as conn:
        conn.execute("CREATE TABLE watchlist (chat_id INTEGER, title TEXT, url TEXT, last_price REAL, source TEXT, updated_at TEXT)")
        conn.execute("INSERT INTO watchlist VALUES (1, 'Test', 'https://example.com/item', 2990, 'test', 'now')")
    monkeypatch.setattr(admin_watchlist, "verify_url", lambda *args, **kwargs: {
        "verified": True,
        "verification_status": "verified",
        "verification_method": "json_ld_product_offer",
        "price": 2490,
        "final_url": "https://example.com/item",
    })
    result = admin_watchlist.verify(1)
    assert result["ok"] is True
    assert result["item"]["last_price"] == 2990
    assert result["verification"]["price"] == 2490


def test_verify_missing_item(monkeypatch, tmp_path):
    db = tmp_path / "watchlist.sqlite3"
    import watchlist_store
    monkeypatch.setattr(watchlist_store, "DB_PATH", str(db))
    import admin_watchlist
    monkeypatch.setattr(admin_watchlist, "DB_PATH", str(db))
    importlib.reload(admin_watchlist)
    with __import__("sqlite3").connect(db) as conn:
        conn.execute("CREATE TABLE watchlist (chat_id INTEGER, title TEXT, url TEXT, last_price REAL, source TEXT, updated_at TEXT)")
    result = admin_watchlist.verify(999)
    assert result == {"ok": False, "error": "not_found", "item_id": 999}
