import importlib


def load(monkeypatch):
    monkeypatch.setenv("PARSER_PUBLIC_URL", "http://parser.test")
    import admin_sources
    return importlib.reload(admin_sources)


def test_snapshot_reports_configured_sources(monkeypatch):
    admin_sources = load(monkeypatch)
    monkeypatch.setenv("OZON_FEED_URL", "https://ozon.example/feed")
    monkeypatch.setenv("WB_API_TOKEN", "token")
    monkeypatch.setenv("YANDEX_MARKET_API_KEY", "key")
    monkeypatch.delenv("SIMALAND_FEED_URL", raising=False)
    monkeypatch.setattr(admin_sources, "_probe", lambda: {"ok": True, "status": "ok", "data": {}})
    data = admin_sources.snapshot()
    assert data["parser"]["ok"] is True
    assert data["configured"]["Ozon"] is True
    assert data["configured"]["Wildberries"] is True
    assert data["configured"]["Яндекс Маркет"] is True
    assert data["configured"]["Sima-Land"] is False


def test_format_text_contains_source_status(monkeypatch):
    admin_sources = load(monkeypatch)
    monkeypatch.setattr(admin_sources, "snapshot", lambda: {
        "parser": {"ok": True, "status": "ok"},
        "configured": {"Ozon": True, "Wildberries": False, "Яндекс Маркет": True, "Sima-Land": False},
    })
    text = admin_sources.format_text()
    assert "🟢 Parser API: ok" in text
    assert "🟢 Ozon: настроен" in text
    assert "⚪ Wildberries: не настроен" in text
    assert "🟢 Яндекс Маркет: настроен" in text
