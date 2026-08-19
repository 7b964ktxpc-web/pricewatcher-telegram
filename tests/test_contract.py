from normalizer import normalize_product


def test_normalized_product_contract_is_stable():
    item = normalize_product(
        source="wildberries",
        marketplace="wildberries",
        product_id="123",
        title="Детская футболка",
        price=1299,
        old_price=1999,
        url="https://www.wildberries.ru/catalog/123/detail.aspx",
    )
    assert item["marketplace"] == "wildberries"
    assert item["id"] == "123"
    assert item["price"] == 1299
    assert item["old_price"] == 1999
    assert item["discount_percent"] == 35
    assert item["url"].startswith("https://")
