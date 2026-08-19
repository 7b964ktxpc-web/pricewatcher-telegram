from __future__ import annotations

import os

# A notification should represent a meaningful saving, not a routine price wobble.
MIN_DROP_PERCENT = max(0.0, float(os.getenv("WATCHLIST_MIN_DROP_PERCENT", "3.0")))
MIN_DROP_AMOUNT = max(0.0, float(os.getenv("WATCHLIST_MIN_DROP_AMOUNT", "100")))


def qualifies(old_price: float | None, new_price: float | None) -> bool:
    if old_price is None or new_price is None or old_price <= 0 or new_price >= old_price:
        return False
    drop = old_price - new_price
    percent = drop / old_price * 100
    return drop >= MIN_DROP_AMOUNT and percent >= MIN_DROP_PERCENT


def describe(old_price: float, new_price: float) -> tuple[float, float]:
    drop = old_price - new_price
    percent = drop / old_price * 100 if old_price else 0.0
    return drop, percent
