from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

from feed_adapters import FEED_ADAPTERS
from marketplace_adapters import ADAPTERS, adapter_status
from normalizer import normalize_product
from source_health import SourceHealthRegistry

UA = os.getenv("PARSER_USER_AGENT", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36")
TIMEOUT = float(os.getenv("PARSER_TIMEOUT", "12"))
RETRIES = max(0, int(os.getenv("PARSER_RETRIES", "2")))
BACKOFF = max(0.0, float(os.getenv("PARSER_BACKOFF", "0.7")))
RETRY_STATUSES = {429, 500, 502, 503, 504}
HEALTH = SourceHealthRegistry(base_cooldown_s=float(os.getenv("SOURCE_COOLDOWN_S", "60")), max_cooldown_s=float(os.getenv("SOURCE_MAX_COOLDOWN_S", "1800")))


@dataclass
class ProviderResult:
    source: str
    marketplace: str
    items: list[dict[str, Any]]
    status: str
    error: str | None = None


class PublicProvider:
    name = "public"
    marketplace = "unknown"

    def search(self, query: str, limit: int = 20) -> ProviderResult:
        raise NotImplementedError

    @staticmethod
    def session() -> requests.Session:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8", "Referer": "https://www.google.com/"})
        return s

    @staticmethod
    def get(session: requests.Session, url: str, **kwargs: Any) -> requests.Response:
        last: Exception | None = None
        for attempt in range(RETRIES + 1):
            try:
                response = session.get(url, timeout=TIMEOUT, **kwargs)
                if response.status_code not in RETRY_STATUSES or attempt >= RETRIES:
                    return response
                if BACKOFF:
                    time.sleep(BACKOFF * (attempt + 1))
            except requests.RequestException as exc:
                last = exc
                if attempt >= RETRIES:
                    raise
                if BACKOFF:
                    time.sleep(BACKOFF * (attempt + 1))
        if last:
            raise last
        raise RuntimeError("request failed")


def _dedupe(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = (str(item.get("marketplace") or ""), str(item.get("product_id") or item.get("id") or item.get("url") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    result.sort(key=lambda x: (x.get("price") is None, x.get("price") if isinstance(x.get("price"), (int, float)) else float("inf")))
    return result[:limit]


class WildberriesProvider(PublicProvider):
    name = "wildberries-public"
    marketplace = "wildberries"

    def search(self, query: str, limit: int = 20) -> ProviderResult:
        if not HEALTH.allow(self.name):
            return ProviderResult(self.name, self.marketplace, [], "cooldown", "source temporarily paused after repeated blocking")
        candidates = [("https://search.wb.ru/exactmatch/ru/common/v9/search", {"resultset": "catalog", "sort": "popular", "suppressSpellcheck": "false"}), ("https://search.wb.ru/exactmatch/ru/common/v7/search", {"resultset": "catalog", "sort": "popular"})]
        common = {"appType": 1, "curr": "rub", "dest": int(os.getenv("WB_DEST", "-1257786")), "page": 1, "query": query, "spp": 30}
        s = self.session()
        last = None
        for url, extra in candidates:
            try:
                r = self.get(s, url, params={**common, **extra})
                last = f"HTTP {r.status_code}"
                if r.status_code != 200:
                    continue
                products = r.json().get("data", {}).get("products", [])
                items = []
                for p in products[:limit]:
                    nm = p.get("id") or p.get("nmId")
                    price = p.get("salePriceU")
                    old = p.get("priceU")
                    if isinstance(price, (int, float)): price /= 100
                    if isinstance(old, (int, float)): old /= 100
                    items.append(normalize_product(source=self.name, marketplace=self.marketplace, product_id=nm, title=p.get("name"), price=price, old_price=old, url=f"https://www.wildberries.ru/catalog/{nm}/detail.aspx" if nm else None, category=p.get("subjectName"), available=True, extra={"brand": p.get("brand"), "rating": p.get("rating"), "feedbacks": p.get("feedbacks")}))
                result = ProviderResult(self.name, self.marketplace, _dedupe(items, limit), "ok")
                HEALTH.record(self.name, result.status)
                return result
            except (requests.RequestException, ValueError) as e:
                last = str(e)
        result = ProviderResult(self.name, self.marketplace, [], "blocked", last or "no response")
        HEALTH.record(self.name, result.status, result.error)
        return result


class OzonProvider(PublicProvider):
    name = "ozon-public"
    marketplace = "ozon"

    def search(self, query: str, limit: int = 20) -> ProviderResult:
        if not HEALTH.allow(self.name):
            return ProviderResult(self.name, self.marketplace, [], "cooldown", "source temporarily paused after repeated blocking")
        try:
            r = self.get(self.session(), f"https://www.ozon.ru/search/?text={quote_plus(query)}", allow_redirects=True)
            if r.status_code != 200:
                result = ProviderResult(self.name, self.marketplace, [], "blocked", f"HTTP {r.status_code}")
            else:
                result = ProviderResult(self.name, self.marketplace, [], "html_only", "catalog page reachable; structured extraction requires an approved feed/adapter")
            HEALTH.record(self.name, result.status, result.error)
            return result
        except requests.RequestException as e:
            result = ProviderResult(self.name, self.marketplace, [], "error", str(e))
            HEALTH.record(self.name, result.status, result.error)
            return result


class SimaLandProvider(PublicProvider):
    name = "simaland-public"
    marketplace = "simaland"

    def search(self, query: str, limit: int = 20) -> ProviderResult:
        if not HEALTH.allow(self.name):
            return ProviderResult(self.name, self.marketplace, [], "cooldown", "source temporarily paused after repeated blocking")
        try:
            r = self.get(self.session(), f"https://www.sima-land.ru/search/?q={quote_plus(query)}", allow_redirects=True)
            if r.status_code != 200:
                result = ProviderResult(self.name, self.marketplace, [], "blocked", f"HTTP {r.status_code}")
            else:
                result = ProviderResult(self.name, self.marketplace, [], "html_only", "search page reachable; use an approved catalog/feed for structured import")
            HEALTH.record(self.name, result.status, result.error)
            return result
        except requests.RequestException as e:
            result = ProviderResult(self.name, self.marketplace, [], "error", str(e))
            HEALTH.record(self.name, result.status, result.error)
            return result


PROVIDERS = {
    "wildberries": WildberriesProvider(),
    "ozon": OzonProvider(),
    "simaland": SimaLandProvider(),
    **FEED_ADAPTERS,
    **ADAPTERS,
}


def source_health() -> list[dict[str, Any]]:
    return HEALTH.snapshot()


def search_sources(query: str, limit: int = 20, sources: list[str] | None = None) -> dict[str, Any]:
    selected = sources or list(PROVIDERS)
    results = []
    for name in selected:
        provider = PROVIDERS.get(name)
        if not provider:
            results.append({"source": name, "status": "unknown_source", "items": [], "error": "Unknown provider"})
            continue
        if name in FEED_ADAPTERS:
            adapter = FEED_ADAPTERS[name]
            result = adapter.search(query, limit)
            results.append({"source": name, "marketplace": adapter.marketplace, **result})
            continue
        if name in ADAPTERS:
            adapter = ADAPTERS[name]
            result = adapter.search(query, limit)
            results.append({"source": name, "marketplace": adapter.marketplace, **result})
            continue
        result = provider.search(query, limit)
        results.append({"source": result.source, "marketplace": result.marketplace, "status": result.status, "items": result.items, "error": result.error})

    items = _dedupe([x for r in results for x in r["items"]], limit)
    return {"query": query, "count": len(items), "items": items, "sources": results, "source_health": source_health(), "marketplace_adapters": adapter_status()}