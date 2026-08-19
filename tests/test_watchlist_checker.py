from watchlist_checker import _best_price, _price


def test_price_accepts_numeric_and_russian_string_formats():
    assert _price({"price": 3990}) == 3990.0
    assert _price({"price": "3 990 ₽"}) == 3990.0
    assert _price({"price": "3990,50 руб."}) == 3990.5
    assert _price({"price": "not-a-price"}) is None


def test_best_price_prefers_exact_watched_url():
    item = {"url": "HTTPS://Example.com/item/1/", "title": "зимняя куртка мальчику"}
    offers = [
        {"url": "https://example.com/item/1/", "price": "4 990 ₽", "title": "зимняя куртка мальчику"},
        {"url": "https://example.com/other", "price": "2 990 ₽", "title": "зимняя куртка мальчику"},
    ]
    assert _best_price(item, offers) == 4990.0


def test_best_price_falls_back_to_matching_title_when_exact_url_is_missing():
    item = {"url": "https://example.com/item/1", "title": "зимняя куртка мальчику"}
    offers = [
        {"url": "https://example.com/other", "price": "4 990 ₽", "title": "зимняя куртка мальчику 3 года"},
        {"url": "https://example.com/third", "price": 2990, "title": "детские кроссовки"},
    ]
    assert _best_price(item, offers) == 4990.0


def test_best_price_does_not_fallback_to_unrelated_offer():
    item = {"url": "https://example.com/item/1"}
    offers = [
        {"url": "https://example.com/other", "price": "4 990 ₽"},
        {"url": "https://example.com/third", "price": 2990},
    ]
    assert _best_price(item, offers) is None
