from price_verifier import verify_url


def test_verify_product_json_ld(monkeypatch):
    page = {
        "ok": True,
        "status": 200,
        "final_url": "https://shop.example/item/1",
        "source": "shop.example",
        "title": "Кроссовки детские",
        "text": "Кроссовки детские 2499 ₽",
        "raw_html": '''<html><head><title>Кроссовки детские</title><script type="application/ld+json">{"@type":"Product","name":"Кроссовки детские","offers":{"price":"2499","priceCurrency":"RUB"}}</script></head><body></body></html>''',
    }
    monkeypatch.setattr("price_verifier.fetch_page", lambda url: page)
    result = verify_url("https://shop.example/item/1", "Кроссовки детские", 2499)
    assert result["verified"] is True
    assert result["price"] == 2499
    assert result["verification_method"] == "json_ld_product_offer"


def test_unverified_when_expected_price_differs(monkeypatch):
    page = {
        "ok": True,
        "status": 200,
        "final_url": "https://shop.example/item/1",
        "source": "shop.example",
        "title": "Кроссовки детские",
        "text": "Кроссовки детские 2499 ₽",
        "raw_html": '''<script type="application/ld+json">{"@type":"Product","name":"Кроссовки детские","offers":{"price":"2499","priceCurrency":"RUB"}}</script>''',
    }
    monkeypatch.setattr("price_verifier.fetch_page", lambda url: page)
    result = verify_url("https://shop.example/item/1", "Кроссовки детские", 1999)
    assert result["verified"] is False
    assert result["price_match"] is False
    assert result["discovery_only"] is True
