from __future__ import annotations

from typing import Any

from agent_web_pipeline import search_web
from child_query_parser import build_search_queries, parse_child_query
from product_offer_matcher import group_offers
from verified_deal_pipeline import build_verified_deals


def _source_name(item: dict[str, Any]) -> str:
    source = item.get("source") or item.get("marketplace") or "web"
    return str(source)


def _sort_key(item: dict[str, Any]) -> tuple[int, float]:
    price = item.get("price")
    return (0, float(price)) if isinstance(price, (int, float)) else (1, float("inf"))


def search_child_deals(text: str, max_results: int = 12) -> dict[str, Any]:
    parsed = parse_child_query(text)
    queries = build_search_queries(parsed)
    discovered: list[dict[str, Any]] = []
    seen: set[str] = set()
    discovery_limit = max(max_results * 2, 24)

    for query in queries:
        result = search_web(query, limit=discovery_limit)
        for item in result.get("items", []):
            url = item.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            discovered.append(item)
            if len(discovered) >= discovery_limit:
                break
        if len(discovered) >= discovery_limit:
            break

    verification_limit = min(discovery_limit, max(max_results, 16))
    verified = build_verified_deals(discovered, limit=verification_limit)
    confirmed = sorted(verified["items"], key=_sort_key)[:max_results]
    grouped = group_offers(confirmed)
    budget = parsed.get("budget_max")
    if budget is not None:
        grouped = [g for g in grouped if g.get("lowest_price") is not None and g["lowest_price"] <= budget]

    sources: dict[str, int] = {}
    for item in confirmed:
        name = _source_name(item)
        sources[name] = sources.get(name, 0) + 1

    return {
        "query": parsed,
        "search_queries": queries,
        "discovered_count": len(discovered),
        "checked_count": verified["checked"],
        "confirmed_count": len(confirmed),
        "confirmed": confirmed,
        "deals": grouped,
        "sources": sources,
        "unverified": verified["unverified"],
        "ready": bool(confirmed),
    }
