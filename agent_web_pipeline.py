from __future__ import annotations

from typing import Any

from web_product_extractor import extract_product_page
from web_research_engine import research


def _normalise_page(page: dict[str, Any], query: str) -> dict[str, Any]:
    """Convert a web discovery page into a safe discovery-only offer."""
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
    result = research(query, limit=limit, fetch_pages=True)
    offers: list[dict[str, Any]] = []
    extracted_pages: list[dict[str, Any]] = []
    for page in result.get("pages", []):
        extracted = extract_product_page(page, query)
        if extracted:
            offers.extend(extracted[:3])
            extracted_pages.append({"url": page.get("final_url") or page.get("url"), "count": len(extracted), "source": page.get("source")})
    if not offers:
        offers = [_normalise_page(item, query) for item in result.get("items", [])]
    return {
        "query": query,
        "count": len(offers),
        "items": offers,
        "pages": result.get("pages", []),
        "extracted_pages": extracted_pages,
        "engines": result.get("engines", []),
        "errors": result.get("errors", []),
        "ready": bool(offers),
    }


def search_web_batch(queries: list[str], limit: int = 8) -> list[dict[str, Any]]:
    return [search_web(query, limit) for query in list(dict.fromkeys(queries))[:4] if query.strip()]
