from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any

import requests

from normalizer import normalize_product

TIMEOUT = float(os.getenv("PARSER_TIMEOUT", "20"))


def _text(node: ET.Element | None, tag: str) -> str | None:
    if node is None:
        return None
    child = node.find(tag)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def parse_yml(xml_bytes: bytes, source: str = "yml", marketplace: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    shop = root.find("shop")
    offers_parent = shop.find("offers") if shop is not None else root.find("offers")
    if offers_parent is None:
        return []
    items = []
    for offer in offers_parent.findall("offer")[:limit]:
        offer_id = offer.attrib.get("id")
        price_text = _text(offer, "price")
        old_text = _text(offer, "oldprice")
        if not offer_id or not price_text:
            continue
        try:
            price = float(price_text.replace(",", "."))
            old = float(old_text.replace(",", ".")) if old_text else None
        except ValueError:
            continue
        title = _text(offer, "name") or _text(offer, "model")
        item = normalize_product(
            source=source,
            marketplace=marketplace,
            product_id=offer_id,
            title=title,
            price=price,
            old_price=old,
            image=_text(offer, "picture"),
            url=_text(offer, "url"),
            category=_text(offer, "categoryId"),
            available=offer.attrib.get("available", "true").lower() == "true",
            extra={
                "vendor": _text(offer, "vendor"),
                "description": _text(offer, "description"),
            },
        )
        items.append(item)
    return items


def fetch_yml(url: str, source: str = "yml", marketplace: str | None = None, limit: int = 100) -> dict[str, Any]:
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "MarketplaceParser/0.2"})
        r.raise_for_status()
        items = parse_yml(r.content, source, marketplace, limit)
        return {"source": source, "marketplace": marketplace, "status": "ok", "count": len(items), "items": items}
    except Exception as e:
        return {"source": source, "marketplace": marketplace, "status": "error", "count": 0, "items": [], "error": str(e)}
