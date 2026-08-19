from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.parse import urlparse

from normalizer import normalize_product

PRICE_RE = re.compile(r"(?<![\d])(?:\d{1,3}(?:[\s\u00a0]\d{3})+|\d{2,6})(?:[,.]\d{1,2})?\s*(?:₽|руб(?:\.|лей)?|RUB)\b", re.I)


def _clean(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _price(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = _clean(value)
    if not text:
        return None
    match = re.search(r"\d[\d\s\u00a0]*(?:[,.]\d+)?", text)
    if not match:
        return None
    raw = match.group(0).replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def _iter_jsonld(raw_html: str):
    for block in re.findall(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", raw_html, re.I | re.S):
        try:
            data = json.loads(html.unescape(block).strip())
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(data, list):
            yield from data
        elif isinstance(data, dict) and isinstance(data.get("@graph"), list):
            yield from data["@graph"]
        else:
            yield data


def _product_nodes(raw_html: str) -> list[dict[str, Any]]:
    nodes = []
    for node in _iter_jsonld(raw_html):
        if not isinstance(node, dict):
            continue
        types = node.get("@type", [])
        types = types if isinstance(types, list) else [types]
        if any(str(t).casefold() == "product" for t in types):
            nodes.append(node)
    return nodes


def _fallback_title(raw_html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.I | re.S)
    return _clean(match.group(1)) if match else None


def _fallback_prices(raw_html: str) -> list[float]:
    prices = []
    for match in PRICE_RE.findall(_clean(raw_html)):
        value = _price(match)
        if value is not None and 1 <= value <= 10_000_000:
            prices.append(value)
    return list(dict.fromkeys(prices))


def extract_product_page(page: dict[str, Any], query: str = "") -> list[dict[str, Any]]:
    raw = str(page.get("raw_html") or "")
    url = page.get("final_url") or page.get("url")
    source = str(page.get("source") or urlparse(str(url)).netloc or "web")
    results: list[dict[str, Any]] = []

    for node in _product_nodes(raw):
        offers = node.get("offers") or {}
        offers = _first(offers)
        if not isinstance(offers, dict):
            offers = {}
        price = _price(offers.get("price"))
        old_price = _price(node.get("priceSpecification", {}).get("price") if isinstance(node.get("priceSpecification"), dict) else None)
        image = _first(node.get("image"))
        product_url = node.get("url") or url
        title = _clean(node.get("name")) or _fallback_title(raw) or query
        availability = str(offers.get("availability") or "").casefold()
        available = None if not availability else not any(x in availability for x in ("outofstock", "soldout", "unavailable"))
        results.append(normalize_product(
            source=source,
            marketplace=source,
            product_id=node.get("sku") or node.get("mpn") or product_url,
            title=title,
            price=price,
            old_price=old_price,
            image=image,
            url=product_url,
            available=available,
            extra={"extraction": "json-ld", "discovery_only": False},
        ))

    if results:
        return results

    title = _fallback_title(raw) or query
    prices = _fallback_prices(raw)
    if not title and not prices:
        return []
    return [normalize_product(
        source=source,
        marketplace=source,
        product_id=url,
        title=title,
        price=prices[0] if prices else None,
        old_price=prices[1] if len(prices) > 1 and prices[1] > prices[0] else None,
        url=url,
        available=None,
        extra={"extraction": "text-fallback", "discovery_only": True, "price_candidates": prices[:8]},
    )]
