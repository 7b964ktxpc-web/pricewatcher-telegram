from __future__ import annotations

from typing import Any

from child_query_parser import build_search_queries, parse_child_query
from product_offer_matcher import group_offers
from verified_deal_pipeline import build_verified_deals
from web_research_engine import search_web


def search_child_deals(text: str, max_results: int = 12) -> dict[str, Any]:
    parsed = parse_child_query(text)
    queries = build_search_queries(parsed)
    discovered: list[dict[str, Any]] = []
    seen: set[str] = set()

    for query in queries:
        for item in search_web(query, max_results=max_results):
            url = item.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            discovered.append(item)
            if len(discovered) >= max_results:
                break
        if len(discovered) >= max_results:
            break

    verified = build_verified_deals(discovered, limit=min(max_results, 8))
    grouped = group_offers(verified["items"])
    budget = parsed.get("budget_max")
    if budget is not None:
        grouped = [g for g in grouped if g.get("lowest_price") is None or g["lowest_price"] <= budget]

    return {
        "query": parsed,
        "search_queries": queries,
        "discovered_count": len(discovered),
        "checked_count": verified["checked"],
        "confirmed_count": verified["count"],
        "deals": grouped,
        "unverified": verified["unverified"],
    }
