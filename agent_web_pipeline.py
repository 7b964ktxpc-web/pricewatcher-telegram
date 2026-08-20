from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from source_search import source_queries
from web_fallback import fallback_search
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
    # Keep one user query plus one purchase-oriented query. The previous
    # implementation expanded to many queries and fetched pages for every
    # query, which could make a single API request exceed production timeouts.
    targeted = source_queries([query, f"{query} купить цена"])
    targeted_queries = [item["query"] for item in targeted[:2]]
    queries = [query, f"{query} купить цена", *targeted_queries]
    unique_queries = list(dict.fromkeys(queries))[:4]

    offers: list[dict[str, Any]] = []
    extracted_pages: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    engines: set[str] = set()

    for search_query in unique_queries:
        result = research(search_query, limit=max(2, min(3, limit)), fetch_pages=True)
        engines.update(result.get("engines", []))
        errors.extend(result.get("errors", []))
        pages.extend(result.get("pages", []))
        for page in result.get("pages", []):
            extracted = extract_product_page(page, query)
            if extracted:
                offers.extend(extracted[:3])
                extracted_pages.append({"url": page.get("final_url") or page.get("url"), "count": len(extracted), "source": page.get("source")})

    failed_pages = [p for p in pages if p.get("page_type") in {"blocked", "rate_limited", "auth_required", "dynamic_page", "timeout", "network_error", "empty_page"}]
    if failed_pages:
        fallback = fallback_search(query, failed_pages, limit=min(4, limit))
        engines.update(fallback.get("engines", []))
        errors.extend(fallback.get("errors", []))
        for item in fallback.get("items", []):
            page = {**item, "text": "", "page_type": "fallback_discovery"}
            extracted = extract_product_page(page, query)
            if extracted:
                offers.extend(extracted[:2])
            else:
                offers.append(_normalise_page(item, query))

    if not offers:
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
        "fallback_used": bool(failed_pages),
        "failed_pages": len(failed_pages),
        "ready": bool(dedup),
    }


def search_web_batch(queries: list[str], limit: int = 8) -> list[dict[str, Any]]:
    unique = [q for q in list(dict.fromkeys(queries))[:2] if q.strip()]
    if not unique:
        return []
    # Search the small query set concurrently so one slow engine does not
    # serialize the whole request.
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(2, len(unique)), thread_name_prefix="web-search") as executor:
        futures = {executor.submit(search_web, query, limit): query for query in unique}
        for future in as_completed(futures):
            query = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"query": query, "count": 0, "items": [], "engines": [], "errors": [{"error": str(exc)}], "ready": False})
    return results
