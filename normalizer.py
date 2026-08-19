from __future__ import annotations

import re
from typing import Any


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("\u00a0", " ")
    if not text:
        return None
    text = re.sub(r"[^0-9,.-]", "", text.replace(" ", ""))
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def normalize_product(*, source: str, marketplace: str | None, product_id: str | int | None,
                      title: str | None, price: float | int | str | None,
                      old_price: float | int | str | None = None, image: str | None = None,
                      url: str | None = None, affiliate_url: str | None = None,
                      category: str | None = None, available: bool | None = None,
                      extra: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_price = _number(price)
    normalized_old_price = _number(old_price)
    discount = None
    if normalized_price is not None and normalized_old_price is not None and normalized_old_price > normalized_price:
        discount = round((1 - normalized_price / normalized_old_price) * 100)
    normalized_id = str(product_id) if product_id is not None else None
    return {
        "id": normalized_id,
        "product_id": normalized_id,
        "source": source, "marketplace": marketplace, "title": title,
        "price": normalized_price, "old_price": normalized_old_price, "discount_percent": discount,
        "image": image, "url": url, "affiliate_url": affiliate_url,
        "category": category, "available": available, "extra": extra or {},
    }
