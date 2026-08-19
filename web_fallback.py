from __future__ import annotations

import re
from typing import Any

from web_research_engine import research

RETRYABLE = {"blocked", "rate_limited", "auth_required", "dynamic_page", "timeout", "network_error", "empty_page"}


def _tokens(text: str) -> str:
    words = re.findall(r"[\wа-яё-]+", (text or "").lower())
    return " ".join(dict.fromkeys(w for w in words if len(w) > 2))


def build_fallback_queries(query: str, pages: list[dict[str, Any]], limit: int = 6) -> list[str]:
    queries = []
    for page in pages:
        if page.get("page_type") not in RETRYABLE:
            continue
        title = _tokens(page.get("title", ""))
        source = page.get("source")
        if title:
            queries.append(f"{title} {query} цена")
            if source and source != "web":
                queries.append(f"{title} {source} цена")
    # Always keep one source-independent retry so a blocked marketplace does not
    # prevent discovery of the same product elsewhere.
    queries.append(f"{query} цена купить скидка")
    return list(dict.fromkeys(queries))[:limit]


def fallback_search(query: str, pages: list[dict[str, Any]], limit: int = 6) -> dict[str, Any]:
    queries = build_fallback_queries(query, pages, limit)
    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    engines: set[str] = set()
    for retry_query in queries:
        result = research(retry_query, limit=3, fetch_pages=False)
        items.extend(result.get("items", []))
        errors.extend(result.get("errors", []))
        engines.update(result.get("engines", []))
    dedup: dict[str, dict[str, Any]] = {}
    for item in items:
        url = item.get("url")
        if url:
            dedup.setdefault(url.split("#", 1)[0], item)
    return {"items": list(dedup.values())[:limit], "queries": queries, "errors": errors, "engines": sorted(engines)}
