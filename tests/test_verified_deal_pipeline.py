from verified_deal_pipeline import build_verified_deals


def test_verified_deals_keep_only_confirmed(monkeypatch):
    def fake_verify(url, expected_title=None, expected_price=None):
        if url.endswith("/good"):
            return {"verified": True, "price": 1200, "discovery_only": False}
        return {"verified": False, "price": 1300, "discovery_only": True}

    monkeypatch.setattr("verified_deal_pipeline.verify_url", fake_verify)
    result = build_verified_deals([
        {"url": "https://shop.test/good", "title": "Товар"},
        {"url": "https://shop.test/bad", "title": "Товар"},
    ])
    assert result["count"] == 1
    assert result["items"][0]["price"] == 1200
    assert len(result["unverified"]) == 1
