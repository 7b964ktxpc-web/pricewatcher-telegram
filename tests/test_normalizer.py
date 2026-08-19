from normalizer import normalize_product


def test_discount_calculation():
    product = normalize_product(
        source="test",
        marketplace="wildberries",
        product_id=123,
        title="Test",
        price=500,
        old_price=1000,
    )
    assert product["id"] == "123"
    assert product["discount_percent"] == 50


def test_no_discount_when_old_price_is_missing():
    product = normalize_product(
        source="test",
        marketplace="ozon",
        product_id="x",
        title="Test",
        price=500,
    )
    assert product["discount_percent"] is None
