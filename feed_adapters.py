from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any

import requests

from normalizer import normalize_product


class FeedAdapter:
    """Read an externally supplied public/partner catalog feed.

    The adapter deliberately does not require seller credentials. A feed URL is
    supplied by deployment configuration and can point at an approved XML/YML
    or JSON catalog export.
    """

    def __init__(self, name: str, marketplace: str | None, env_name: str):
        self.name = name
        self.marketplace = marketplace
        self.env_name = env_name

    def configured(self) -> bool:
        return bool(os.getenv(self.env_name, "").strip())

    def search(self, query: str, limit: int = 20) -> dict[str, Any]:
        url = os.getenv(self.env_name, "").strip()
        if not url:
            return {"status": "not_configured", "items": [], "error": f"Set {self.env_name} to an approved catalog/feed URL"}

        try:
            r = requests.get(url, timeout=float(os.getenv("PARSER_TIMEOUT", "20")), headers={
                "User-Agent": os.getenv("PARSER_USER_AGENT", "MarketplaceParser/1.0"),
                "Accept": "application/json, application/xml, text/xml, */*",
            })
            r.raise_for_status()
            items = self._parse(r.text, r.headers.get("content-type", ""))
            q = query.casefold().split()
            if q:
                items = [x for x in items if all(word in str(x.get("title", "")).casefold() for word in q)]
            return {"status": "ok", "items": items[:limit], "error": None}
        except (requests.RequestException, ValueError, ET.ParseError) as exc:
            return {"status": "error", "items": [], "error": str(exc)}

    def _parse(self, text: str, content_type: str) -> list[dict[str, Any]]:
        stripped = text.lstrip()
        if "json" in content_type or stripped.startswith("[") or stripped.startswith("{"):
            import json
            payload = json.loads(text)
            raw = payload.get("products", payload.get("items", payload if isinstance(payload, list) else []))
        else:
            root = ET.fromstring(text)
            raw = []
            for offer in root.findall(".//offer"):
                raw.append({
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

        out = []
        for p in raw if isinstance(raw, list) else []:
            if not isinstance(p, dict):
                continue
            out.append(normalize_product(
                source=self.name,
                marketplace=self.marketplace,
                product_id=p.get("id") or p.get("sku") or p.get("offer_id"),
                title=p.get("title") or p.get("name"),
                price=p.get("price"),
                old_price=p.get("old_price") or p.get("oldprice"),
                url=p.get("url"),
                category=p.get("category"),
                available=p.get("available", True),
                extra={"description": p.get("description"), "image": p.get("image") or p.get("picture")},
            ))
        return out


FEED_ADAPTERS = {
    "wildberries_feed": FeedAdapter("wildberries-feed", "wildberries", "WB_FEED_URL"),
    "ozon_feed": FeedAdapter("ozon-feed", "ozon", "OZON_FEED_URL"),
    "yandex_market_feed": FeedAdapter("yandex-market-feed", "yandex_market", "YANDEX_MARKET_FEED_URL"),
    "simaland_feed": FeedAdapter("simaland-feed", "simaland", "SIMALAND_FEED_URL"),
    "detmir_feed": FeedAdapter("detmir-feed", None, "DETMIR_FEED_URL"),
    "akusherstvo_feed": FeedAdapter("akusherstvo-feed", None, "AKUSHERSTVO_FEED_URL"),
    "korablik_feed": FeedAdapter("korablik-feed", None, "KORABLIK_FEED_URL"),
}
