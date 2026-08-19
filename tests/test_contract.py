from normalizer import normalize_item


def test_normalized_product_contract_is_stable():
    item = normalize_item({
        "marketplace": "wildberries",
        "product_id": "123",
        "name": " Детская футболка ",
        "price": "1 299 ₽",
        "old_price": "1 999 ₽",
        "url": "https://www.wildberries.ru/catalog/123/detail.aspx",
    })
    assert item["marketplace"] == "wildberries"
    assert item["product_id"] == "123"
    assert item["price"] == 1299
    assert item["old_price"] == 1999
    assert item["url"].startswith("https://")
