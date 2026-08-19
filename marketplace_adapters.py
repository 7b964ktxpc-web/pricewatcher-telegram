from __future__ import annotations

import os
from typing import Any

import requests

from normalizer import normalize_product


TIMEOUT = float(os.getenv("PARSER_TIMEOUT", "12"))


class MarketplaceAdapter:
    name = "marketplace"
    marketplace = "unknown"

    def configured(self) -> bool:
        return False

    def health(self) -> dict[str, Any]:
        return {"source": self.name, "marketplace": self.marketplace, "configured": self.configured()}

    def search(self, query: str, limit: int = 20) -> dict[str, Any]:
        return {"status": "not_configured", "items": [], "error": "credentials are not configured"}


class WildberriesSellerAdapter(MarketplaceAdapter):
    name = "wildberries-api"
    marketplace = "wildberries"
    base = "https://discounts-prices-api.wildberries.ru"

    def configured(self) -> bool:
        return bool(os.getenv("WB_API_TOKEN"))

    def search(self, query: str, limit: int = 20) -> dict[str, Any]:
        # WB seller API exposes the authenticated seller's catalog/prices, not a public marketplace search.
        # We therefore use it as an authoritative price/stock enrichment adapter for products belonging to the account.
        if not self.configured():
            return {"status": "not_configured", "items": [], "error": "WB_API_TOKEN is not configured"}
        try:
            headers = {"Authorization": os.environ["WB_API_TOKEN"]}
            r = requests.get(
                f"{self.base}/api/v2/list/goods/filter",
                headers=headers,
                params={"limit": min(max(limit, 1), 1000), "offset": 0},
                timeout=TIMEOUT,
            )
            if r.status_code != 200:
                return {"status": "error", "items": [], "error": f"HTTP {r.status_code}: {r.text[:300]}"}
            goods = r.json().get("data", {}).get("listGoods", [])
            needle = query.casefold().split()
            items = []
            for p in goods:
                text = " ".join(str(p.get(k) or "") for k in ("vendorCode", "nmID", "objectName" )).casefold()
                if needle and not all(token in text for token in needle):
                    continue
                sizes = p.get("sizes") or [{}]
                size = sizes[0] if isinstance(sizes[0], dict) else {}
                price = size.get("discountedPrice") or size.get("price")
                old = size.get("price")
                nm = p.get("nmID")
                items.append(normalize_product(
                    source=self.name,
                    marketplace=self.marketplace,
                    product_id=nm,
                    title=p.get("objectName") or p.get("vendorCode") or f"WB {nm}",
                    price=price,
                    old_price=old,
                    url=f"https://www.wildberries.ru/catalog/{nm}/detail.aspx" if nm else None,
                    category=p.get("objectName"),
                    available=True,
                    extra={"vendor_code": p.get("vendorCode"), "discount": p.get("discount")},
                ))
            return {"status": "ok", "items": items[:limit], "error": None}
        except (requests.RequestException, ValueError) as exc:
            return {"status": "error", "items": [], "error": str(exc)}


class YandexMarketPartnerAdapter(MarketplaceAdapter):
    name = "yandex-market-api"
    marketplace = "yandex_market"
    base = "https://api.partner.market.yandex.ru"

    def configured(self) -> bool:
        return bool(os.getenv("YANDEX_MARKET_API_KEY") and os.getenv("YANDEX_MARKET_BUSINESS_ID"))

    def search(self, query: str, limit: int = 20) -> dict[str, Any]:
        # Partner API returns the authenticated business catalog. It is intentionally not treated as public search.
        if not self.configured():
            return {"status": "not_configured", "items": [], "error": "YANDEX_MARKET_API_KEY and YANDEX_MARKET_BUSINESS_ID are required"}
        try:
            business_id = os.environ["YANDEX_MARKET_BUSINESS_ID"]
            headers = {"Api-Key": os.environ["YANDEX_MARKET_API_KEY"], "Content-Type": "application/json"}
            r = requests.post(
                f"{self.base}/v2/businesses/{business_id}/offer-mappings",
                headers=headers,
                params={"language": "RU", "limit": min(max(limit, 1), 100)},
                json={},
                timeout=TIMEOUT,
            )
            if r.status_code != 200:
                return {"status": "error", "items": [], "error": f"HTTP {r.status_code}: {r.text[:300]}"}
            data = r.json().get("result", {})
            mappings = data.get("offerMappings", [])
            needle = query.casefold().split()
            items = []
            for mapping in mappings:
                offer = mapping.get("offer", mapping)
                text = " ".join(str(offer.get(k) or "") for k in ("name", "vendor", "shopSku")).casefold()
                if needle and not all(token in text for token in needle):
                    continue
                items.append(normalize_product(
                    source=self.name,
                    marketplace=self.marketplace,
                    product_id=offer.get("shopSku") or mapping.get("marketSku"),
                    title=offer.get("name"),
                    price=(offer.get("price") or {}).get("value") if isinstance(offer.get("price"), dict) else offer.get("price"),
                    old_price=None,
                    url=offer.get("url"),
                    category=offer.get("category"),
                    available=True,
                    extra={"market_sku": mapping.get("marketSku"), "vendor": offer.get("vendor")},
                ))
            return {"status": "ok", "items": items[:limit], "error": None}
        except (requests.RequestException, ValueError) as exc:
            return {"status": "error", "items": [], "error": str(exc)}


ADAPTERS = {
    "wildberries-api": WildberriesSellerAdapter(),
    "yandex-market-api": YandexMarketPartnerAdapter(),
}


def adapter_status() -> list[dict[str, Any]]:
    return [adapter.health() for adapter in ADAPTERS.values()]
