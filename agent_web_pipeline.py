from __future__ import annotations

from typing import Any

from source_search import source_queries
from web_product_extractor import extract_product_page
from web_research_engine import research


def _normalise_page(page: dict[str, Any], query: str) -> dict[str, Any]:
    return {
        "title": page.get("title") or query,
        "url": page.get("final_url") or page.get("url"),
        "source": page.get("source") or "web",
        "marketplace": page.get("source") or "web",
        "discovery_only": True,
        "web_status": page.get("status"),
        "page_text_available": bool(page.get("text")),
    }


def search_web(query: str, limit: int = 8) -> dict[str, Any]:
    targeted = source_queries([query, f"{query} купить цена", f"{query} скидка акция"])
    targeted_queries = [item["query"] for item in targeted]
    # Keep the generic searches as a fallback for ordinary children's stores.
    queries = [query, f"{query} купить цена", f"{query} скидка акция", *targeted_queries]
    unique_queries = list(dict.fromkeys(queries))

    offers: list[dict[str, Any]] = []
    extracted_pages: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    engines: set[str] = set()

    # Limit per-query results so one source cannot consume the complete budget.
    for search_query in unique_queries:
        result = research(search_query, limit=max(2, min(4, limit)), fetch_pages=True)
        engines.update(result.get("engines", []))
        errors.extend(result.get("errors", []))
        pages.extend(result.get("pages", []))
        for page in result.get("pages", []):
            extracted = extract_product_page(page, query)
            if extracted:
                offers.extend(extracted[:3])
                extracted_pages.append({"url": page.get("final_url") or page.get("url"), "count": len(extracted), "source": page.get("source")})

    if not offers:
        # Discovery-only fallback; these entries must not be treated as verified prices.
        discovered = research(query, limit=limit, fetch_pages=False)
        offers = [_normalise_page(item, query) for item in discovered.get("items", [])]
        engines.update(discovered.get("engines", []))
        errors.extend(discovered.get("errors", []))

    dedup: dict[str, dict[str, Any]] = {}
    for offer in offers:
        key = offer.get("url") or f"{offer.get('title')}|{offer.get('price')}"
        dedup.setdefault(key, offer)

    return {
        "query": query,
        "count": len(dedup),
        "items": list(dedup.values())[: max(1, limit * 2)],
        "pages": pages,
        "extracted_pages": extracted_pages,
        "engines": sorted(engines),
        "errors": errors,
        "ready": bool(dedup),
    }


def search_web_batch(queries: list[str], limit: int = 8) -> list[dict[str, Any]]:
    return [search_web(query, limit) for query in list(dict.fromkeys(queries))[:4] if query.strip()]
