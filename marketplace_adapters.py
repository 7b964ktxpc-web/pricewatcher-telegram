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
                text = " ".join(str(p.get(k) or "") for k in ("vendorCode", "nmID", "objectName")).casefold()
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

    @staticmethod
    def _price_map(session: requests.Session, headers: dict[str, str], business_id: str, offer_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not offer_ids:
            return {}
        prices: dict[str, dict[str, Any]] = {}
        for start in range(0, len(offer_ids), 200):
            batch = offer_ids[start:start + 200]
            response = session.post(
                f"https://api.partner.market.yandex.ru/v2/businesses/{business_id}/offer-prices",
                headers=headers,
                json={"offerIds": batch},
                timeout=TIMEOUT,
            )
            if response.status_code != 200:
                continue
            for row in response.json().get("result", {}).get("offers", []):
                offer_id = str(row.get("offerId") or "")
                price = row.get("price") or {}
                if offer_id:
                    prices[offer_id] = price
        return prices

    def search(self, query: str, limit: int = 20) -> dict[str, Any]:
        if not self.configured():
            return {"status": "not_configured", "items": [], "error": "YANDEX_MARKET_API_KEY and YANDEX_MARKET_BUSINESS_ID are required"}
        try:
            business_id = os.environ["YANDEX_MARKET_BUSINESS_ID"]
            headers = {"Api-Key": os.environ["YANDEX_MARKET_API_KEY"], "Content-Type": "application/json"}
            session = requests.Session()
            mappings: list[dict[str, Any]] = []
            page_token = None
            max_items = min(max(limit * 5, limit), 500)
            while len(mappings) < max_items:
                params: dict[str, Any] = {"language": "RU", "limit": min(max_items - len(mappings), 100)}
                if page_token:
                    params["pageToken"] = page_token
                r = session.post(
                    f"{self.base}/v2/businesses/{business_id}/offer-mappings",
                    headers=headers,
                    params=params,
                    json={},
                    timeout=TIMEOUT,
                )
                if r.status_code != 200:
                    return {"status": "error", "items": [], "error": f"HTTP {r.status_code}: {r.text[:300]}"}
                data = r.json().get("result", {})
                page = data.get("offerMappings", [])
                mappings.extend(page)
                page_token = (data.get("paging") or {}).get("nextPageToken")
                if not page_token or not page:
                    break

            needle = query.casefold().split()
            candidates = []
            for mapping in mappings:
                offer = mapping.get("offer") or {}
                offer_id = str(offer.get("offerId") or "")
                text = " ".join(str(offer.get(k) or "") for k in ("name", "vendor", "vendorCode", "offerId")).casefold()
                if needle and not all(token in text for token in needle):
                    continue
                candidates.append((mapping, offer, offer_id))

            price_map = self._price_map(session, headers, business_id, [x[2] for x in candidates if x[2]])
            items = []
            for mapping, offer, offer_id in candidates:
                price = price_map.get(offer_id, {})
                showcase = mapping.get("showcaseUrls") or []
                url = None
                if showcase and isinstance(showcase[0], dict):
                    url = showcase[0].get("showcaseUrl")
                items.append(normalize_product(
                    source=self.name,
                    marketplace=self.marketplace,
                    product_id=offer_id or mapping.get("mapping", {}).get("marketSku"),
                    title=offer.get("name"),
                    price=price.get("value"),
                    old_price=price.get("discountBase"),
                    url=url,
                    category=offer.get("category"),
                    available=True,
                    extra={
                        "market_sku": mapping.get("mapping", {}).get("marketSku"),
                        "vendor": offer.get("vendor"),
                        "vendor_code": offer.get("vendorCode"),
                        "currency": price.get("currencyId"),
                        "price_updated_at": price.get("updatedAt"),
                    },
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
