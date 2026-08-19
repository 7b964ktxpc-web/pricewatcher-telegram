from __future__ import annotations

from typing import Any


def normalize_product(*, source: str, marketplace: str | None, product_id: str | int | None,
                      title: str | None, price: float | int | None,
                      old_price: float | int | None = None, image: str | None = None,
                      url: str | None = None, affiliate_url: str | None = None,
                      category: str | None = None, available: bool | None = None,
                      extra: dict[str, Any] | None = None) -> dict[str, Any]:
    discount = None
    if price is not None and old_price is not None and old_price > price:
        discount = round((1 - float(price) / float(old_price)) * 100)
    normalized_id = str(product_id) if product_id is not None else None
    return {
        "id": normalized_id,
        "product_id": normalized_id,
        "source": source, "marketplace": marketplace, "title": title,
        "price": price, "old_price": old_price, "discount_percent": discount,
        "image": image, "url": url, "affiliate_url": affiliate_url,
        "category": category, "available": available, "extra": extra or {},
    }
