from watchlist_checker import _best_price, _price


def test_price_accepts_numeric_and_russian_string_formats():
    assert _price({"price": 3990}) == 3990.0
    assert _price({"price": "3 990 ₽"}) == 3990.0
    assert _price({"price": "3990,50 руб."}) == 3990.5
    assert _price({"price": "not-a-price"}) is None


def test_best_price_prefers_exact_watched_url():
    item = {"url": "HTTPS://Example.com/item/1/"}
    offers = [
        {"url": "https://example.com/item/1/", "price": "4 990 ₽"},
        {"url": "https://example.com/other", "price": "2 990 ₽"},
    ]
    assert _best_price(item, offers) == 4990.0


def test_best_price_falls_back_when_exact_url_is_missing():
    item = {"url": "https://example.com/item/1"}
    offers = [
        {"url": "https://example.com/other", "price": "4 990 ₽"},
        {"url": "https://example.com/third", "price": 2990},
    ]
    assert _best_price(item, offers) == 2990.0
