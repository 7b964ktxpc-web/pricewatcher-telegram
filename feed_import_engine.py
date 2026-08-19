from __future__ import annotations

import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import requests

from feed_adapters import FEED_ADAPTERS
from normalizer import normalize_product


@dataclass
class ImportResult:
    source: str
    status: str
    fetched: int = 0
    accepted: int = 0
    skipped: int = 0
    duration_ms: int = 0
    error: str | None = None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("products", "items", "offers", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def _parse_xml(text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(text)
    items: list[dict[str, Any]] = []
    for offer in root.findall(".//offer"):
        items.append({
            "id": offer.attrib.get("id"),
            "title": offer.findtext("name") or offer.findtext("model") or "",
            "price": offer.findtext("price"),
            "old_price": offer.findtext("oldprice"),
            "url": offer.findtext("url"),
            "available": offer.attrib.get("available", "true") != "false",
            "category": offer.findtext("categoryId"),
            "description": offer.findtext("description"),
            "image": offer.findtext("picture"),
        })
    return items


def _parse_payload(text: str, content_type: str) -> list[dict[str, Any]]:
    stripped = text.lstrip()
    if "json" in content_type.lower() or stripped.startswith("{") or stripped.startswith("["):
        return _as_items(json.loads(text))
    return _parse_xml(text)


def _stable_id(item: dict[str, Any]) -> str:
    raw = _text(item.get("id") or item.get("sku") or item.get("offer_id") or item.get("url"))
    if raw:
        return raw
    basis = "|".join(_text(item.get(k)) for k in ("title", "price", "url"))
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:20]


def normalize_feed_items(source: str, marketplace: str | None, raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_items:
        product_id = _stable_id(item)
        if product_id in seen:
            continue
        seen.add(product_id)
        result.append(normalize_product(
            source=source,
            marketplace=marketplace,
            product_id=product_id,
            title=item.get("title") or item.get("name") or item.get("model"),
            price=item.get("price"),
            old_price=item.get("old_price") or item.get("oldprice"),
            url=item.get("url"),
            category=item.get("category") or item.get("category_name"),
            available=item.get("available", True),
            extra={
                "description": item.get("description"),
                "image": item.get("image") or item.get("picture"),
                "sku": item.get("sku"),
            },
        ))
    return result


def import_feed(source: str, limit: int = 5000) -> tuple[ImportResult, list[dict[str, Any]]]:
    started = time.monotonic()
    adapter = FEED_ADAPTERS.get(source)
    if not adapter:
        return ImportResult(source, "unknown_source"), []
    url = os.getenv(adapter.env_name, "").strip()
    if not url:
        return ImportResult(source, "not_configured"), []

    try:
        response = requests.get(url, timeout=float(os.getenv("FEED_IMPORT_TIMEOUT", "30")), headers={
            "User-Agent": os.getenv("PARSER_USER_AGENT", "MarketplaceParser/1.0"),
            "Accept": "application/xml, text/xml, application/json, */*",
        })
        response.raise_for_status()
        raw = _parse_payload(response.text, response.headers.get("content-type", ""))[:limit]
        products = normalize_feed_items(source, adapter.marketplace, raw)
        return ImportResult(source, "ok", len(raw), len(products), len(raw) - len(products), int((time.monotonic()-started)*1000)), products
    except (requests.RequestException, ValueError, ET.ParseError, UnicodeError) as exc:
        return ImportResult(source, "error", duration_ms=int((time.monotonic()-started)*1000), error=str(exc)), []


def import_all(configured_only: bool = True, limit: int = 5000) -> dict[str, Any]:
    sources = list(FEED_ADAPTERS)
    if configured_only:
        sources = [name for name in sources if os.getenv(FEED_ADAPTERS[name].env_name, "").strip()]
    results: list[ImportResult] = []
    products: list[dict[str, Any]] = []
    for source in sources:
        result, items = import_feed(source, limit)
        results.append(result)
        products.extend(items)
    return {
        "sources": [r.__dict__ for r in results],
        "count": len(products),
        "items": products,
        "ready": any(r.status == "ok" and r.accepted > 0 for r in results),
    }
