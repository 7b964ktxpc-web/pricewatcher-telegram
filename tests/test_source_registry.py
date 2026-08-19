from source_registry import registry


def test_source_registry_contains_core_marketplaces_and_child_stores():
    sources = registry()
    assert {"wildberries", "ozon", "yandex_market", "simaland"}.issubset(sources)
    assert {"detmir", "akusherstvo", "korablik"}.issubset(sources)


def test_source_registry_does_not_enable_unconfigured_feeds(monkeypatch):
    monkeypatch.delenv("DETMIR_FEED_URL", raising=False)
    from source_registry import source_status

    detmir = next(x for x in source_status() if x["key"] == "detmir")
    assert detmir["configured"] is False
    assert detmir["runtime_enabled"] is False
