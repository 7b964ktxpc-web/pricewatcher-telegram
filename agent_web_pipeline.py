from __future__ import annotations

from typing import Any

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
    offers = [_normalise_page(item, query) for item in result.get("items", [])]
    pages = result.get("pages", [])
    return {
        "query": query,
        "count": len(offers),
        "items": offers,
        "pages": pages,
        "engines": result.get("engines", []),
        "errors": result.get("errors", []),
        "ready": bool(offers),
    }


def search_web_batch(queries: list[str], limit: int = 8) -> list[dict[str, Any]]:
    # Kept intentionally small: web pages are discovery evidence and should not
    # dominate the authoritative feed/API results.
    return [search_web(query, limit) for query in list(dict.fromkeys(queries))[:4] if query.strip()]
