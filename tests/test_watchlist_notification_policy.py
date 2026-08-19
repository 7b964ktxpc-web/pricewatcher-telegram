from watchlist_notification_policy import qualifies, describe


def test_qualifies_requires_both_thresholds():
    assert qualifies(5000, 4900) is False
    assert qualifies(5000, 4950) is False


def test_qualifies_accepts_meaningful_drop():
    assert qualifies(5000, 4700) is True


def test_qualifies_rejects_price_increase_and_invalid_prices():
    assert qualifies(5000, 5100) is False
    assert qualifies(None, 4000) is False
    assert qualifies(0, 100) is False


def test_describe_returns_amount_and_percent():
    drop, percent = describe(5000, 4500)
    assert drop == 500
    assert percent == 10.0
