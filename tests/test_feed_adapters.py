import json

from feed_adapters import FeedAdapter


def test_json_feed_filters_and_normalizes(monkeypatch):
    payload = json.dumps({"products": [
        {"id": "1", "title": "Детская футболка мальчик", "price": "599", "old_price": "999", "url": "https://example.test/1"},
        {"id": "2", "title": "Женские брюки", "price": "1000", "url": "https://example.test/2"},
    ]})

    class Response:
        headers = {"content-type": "application/json"}
        def raise_for_status(self): pass
        @property
        def text(self): return payload

    import feed_adapters
    monkeypatch.setattr(feed_adapters.requests, "get", lambda *a, **k: Response())
    monkeypatch.setenv("TEST_FEED_URL", "https://example.test/feed.json")

    result = FeedAdapter("test-feed", "test", "TEST_FEED_URL").search("футболка мальчик")
    assert result["status"] == "ok"
    assert len(result["items"]) == 1
    assert result["items"][0]["product_id"] == "1"
    assert result["items"][0]["price"] == 599.0


def test_xml_feed_parses(monkeypatch):
    xml = '''<yml_catalog><shop><offers><offer id="7" available="true"><name>Детская куртка</name><price>1999</price><oldprice>2999</oldprice><url>https://example.test/7</url><picture>https://example.test/7.jpg</picture></offer></offers></shop></yml_catalog>'''

    class Response:
        headers = {"content-type": "application/xml"}
        def raise_for_status(self): pass
        @property
        def text(self): return xml

    import feed_adapters
    monkeypatch.setattr(feed_adapters.requests, "get", lambda *a, **k: Response())
    monkeypatch.setenv("TEST_FEED_URL", "https://example.test/feed.xml")

    result = FeedAdapter("test-feed", "test", "TEST_FEED_URL").search("куртка")
    assert result["status"] == "ok"
    assert len(result["items"]) == 1
    assert result["items"][0]["product_id"] == "7"
    assert result["items"][0]["price"] == 1999.0
