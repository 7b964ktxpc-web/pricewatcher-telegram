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
        if not self.configured():
            return {"status": "not_configured", "items": [], "error": "WB_API_TOKEN is not configured"}
        try:
            headers = {"Authorization": os.environ["WB_API_TOKEN"]}
            r = requests.get(f"{self.base}/api/v2/list/goods/filter", headers=headers, params={"limit": min(max(limit, 1), 1000), "offset": 0}, timeout=TIMEOUT)
            if r.status_code != 200:
                return {"status": "error", "items": [], "error": f"HTTP {r.status_code}: {r.text[:300]}"}
            goods = r.json().get("data", {}).get("listGoods", [])
            needle = query.casefold().split()
            items = []
            for p in goods:
                text = " ".join(str(p.get(k) or "") for k in ("vendorCode", "nmID", "objectName")).casefold()
                if needle and not all(token in text for token in needle):
                    continue
                sizes = p.get("sizes") or [{}]
                size = sizes[0] if isinstance(sizes[0], dict) else {}
                price = size.get("discountedPrice") or size.get("price")
                old = size.get("price")
                nm = p.get("nmID")
                items.append(normalize_product(source=self.name, marketplace=self.marketplace, product_id=nm, title=p.get("objectName") or p.get("vendorCode") or f"WB {nm}", price=price, old_price=old, url=f"https://www.wildberries.ru/catalog/{nm}/detail.aspx" if nm else None, category=p.get("objectName"), available=True, extra={"vendor_code": p.get("vendorCode"), "discount": p.get("discount")}))
            return {"status": "ok", "items": items[:limit], "error": None}
        except (requests.RequestException, ValueError) as exc:
            return {"status": "error", "items": [], "error": str(exc)}


ADAPTERS = {
    "wildberries-api": WildberriesSellerAdapter(),
}


def adapter_status() -> list[dict[str, Any]]:
    return [adapter.health() for adapter in ADAPTERS.values()]