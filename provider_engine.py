from __future__ import annotations

import os
import time
from typing import Any

import requests

from feed_adapters import FEED_ADAPTERS
from normalizer import normalize_product

UA = os.getenv("PARSER_USER_AGENT", "MarketplaceParser/1.0")
TIMEOUT = float(os.getenv("PARSER_TIMEOUT", "12"))
RETRIES = max(0, int(os.getenv("PARSER_RETRIES", "2")))
BACKOFF = max(0.0, float(os.getenv("PARSER_BACKOFF", "0.7")))
RETRY_STATUSES = {429, 500, 502, 503, 504}


def _request(url: str, params: dict[str, Any] | None = None) -> requests.Response:
    headers = {"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"}
    last: Exception | None = None
    with requests.Session() as session:
        session.headers.update(headers)
        for attempt in range(RETRIES + 1):
            try:
                response = session.get(url, params=params, timeout=TIMEOUT, allow_redirects=True)
                if response.status_code not in RETRY_STATUSES or attempt >= RETRIES:
                    return response
                retry_after = response.headers.get("Retry-After")
                delay = min(float(retry_after), 15.0) if retry_after and retry_after.isdigit() else BACKOFF * (attempt + 1)
                time.sleep(delay)
            except requests.RequestException as exc:
                last = exc
                if attempt >= RETRIES:
                    raise
                time.sleep(BACKOFF * (attempt + 1))
    raise last or RuntimeError("request failed")


def _text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(k) or "") for k in ("title", "category", "description", "brand")).casefold()


def _matches(item: dict[str, Any], query: str) -> bool:
    haystack = _text(item)
    return all(word in haystack for word in query.casefold().split() if len(word) > 1)


def _dedupe(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique = []
    for item in items:
        key = (str(item.get("marketplace") or ""), str(item.get("id") or item.get("url") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    unique.sort(key=lambda x: (x.get("price") is None, x.get("price") if isinstance(x.get("price"), (int, float)) else float("inf"), -(x.get("discount_percent") or 0)))
    return unique[:limit]


def search_wb(query: str, limit: int) -> dict[str, Any]:
    common = {"appType": 1, "curr": "rub", "dest": int(os.getenv("WB_DEST", "-1257786")), "page": 1, "query": query, "spp": 30}
    for endpoint, extra in [("https://search.wb.ru/exactmatch/ru/common/v9/search", {"resultset": "catalog", "sort": "popular", "suppressSpellcheck": "false"}), ("https://search.wb.ru/exactmatch/ru/common/v7/search", {"resultset": "catalog", "sort": "popular"})]:
        try:
            r = _request(endpoint, {**common, **extra})
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
                items.append(normalize_product(source="wildberries-public", marketplace="wildberries", product_id=nm, title=p.get("name"), price=price, old_price=old, url=f"https://www.wildberries.ru/catalog/{nm}/detail.aspx" if nm else None, category=p.get("subjectName"), available=True, extra={"brand": p.get("brand"), "rating": p.get("rating"), "feedbacks": p.get("feedbacks")}))
            return {"source": "wildberries-public", "marketplace": "wildberries", "status": "ok", "items": _dedupe(items, limit), "error": None}
        except (requests.RequestException, ValueError) as exc:
            last = str(exc)
    return {"source": "wildberries-public", "marketplace": "wildberries", "status": "blocked", "items": [], "error": locals().get("last", "no response")}


def search_public_page(name: str, marketplace: str, url: str) -> dict[str, Any]:
    try:
        r = _request(url)
        if r.status_code != 200:
            return {"source": name, "marketplace": marketplace, "status": "blocked", "items": [], "error": f"HTTP {r.status_code}"}
        return {"source": name, "marketplace": marketplace, "status": "html_only", "items": [], "error": "Page reachable, but no approved structured catalog adapter is configured"}
    except requests.RequestException as exc:
        return {"source": name, "marketplace": marketplace, "status": "error", "items": [], "error": str(exc)}


def search_sources(query: str, limit: int = 20, sources: list[str] | None = None) -> dict[str, Any]:
    selected = sources or ["wildberries", "ozon", "yandex_market", "simaland", *FEED_ADAPTERS]
    results: list[dict[str, Any]] = []
    for name in selected:
        if name == "wildberries":
            result = search_wb(query, limit)
        elif name == "ozon":
            from urllib.parse import quote_plus
            result = search_public_page("ozon-public", "ozon", f"https://www.ozon.ru/search/?text={quote_plus(query)}")
        elif name == "yandex_market":
            from urllib.parse import quote_plus
            result = search_public_page("yandex-market-public", "yandex_market", f"https://market.yandex.ru/search?text={quote_plus(query)}")
        elif name == "simaland":
            from urllib.parse import quote_plus
            result = search_public_page("simaland-public", "simaland", f"https://www.sima-land.ru/search/?q={quote_plus(query)}")
        elif name in FEED_ADAPTERS:
            adapter = FEED_ADAPTERS[name]
            result = {"source": name, "marketplace": adapter.marketplace, **adapter.search(query, limit)}
        else:
            result = {"source": name, "status": "unknown_source", "items": [], "error": "Unknown provider"}
        results.append(result)

    items = _dedupe([item for result in results for item in result.get("items", []) if _matches(item, query)], limit)
    return {"query": query, "count": len(items), "items": items, "sources": results}
