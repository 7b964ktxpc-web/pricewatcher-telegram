from web_product_extractor import extract_product_page


def test_extract_jsonld_product():
    html = '''
    <html><head><title>Футболка детская</title>
    <script type="application/ld+json">
    {"@type":"Product","name":"Футболка для мальчика","sku":"wb-123",
     "image":"https://example.com/a.jpg","offers":{"price":1299,"availability":"https://schema.org/InStock"}}
    </script></head><body></body></html>
    '''
    result = extract_product_page({"raw_html": html, "url": "https://www.wildberries.ru/catalog/123/detail.aspx", "source": "wildberries"}, "футболка")
    assert len(result) == 1
    assert result[0]["title"] == "Футболка для мальчика"
    assert result[0]["price"] == 1299.0
    assert result[0]["available"] is True
    assert result[0]["extra"]["extraction"] == "json-ld"
    assert result[0]["extra"]["discovery_only"] is False


def test_extract_fallback_price_is_marked_discovery_only():
    html = '<html><head><title>Куртка детская</title></head><body>Цена 2 499 ₽</body></html>'
    result = extract_product_page({"raw_html": html, "url": "https://example.org/p/1", "source": "example.org"}, "куртка")
    assert len(result) == 1
    assert result[0]["title"] == "Куртка детская"
    assert result[0]["price"] == 2499.0
    assert result[0]["extra"]["discovery_only"] is True


def test_empty_page_returns_no_offer():
    result = extract_product_page({"raw_html": "", "url": "https://example.org"}, "детские товары")
    assert result == []
