from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from feed_adapters import FEED_ADAPTERS
from providers import PROVIDERS
from source_health import HEALTH


def _run_source(source: str, query: str, limit: int) -> dict[str, Any]:
    if not HEALTH.allow(source):
        return {
            "source": source,
            "status": "cooldown",
            "items": [],
            "error": "Source temporarily paused by circuit breaker",
        }

    provider = PROVIDERS.get(source)
    if provider is None:
        return {
            "source": source,
            "status": "unknown_source",
            "items": [],
            "error": "Unknown provider",
        }

    try:
        if source in FEED_ADAPTERS:
            result = provider.search(query, limit)
            status = str(result.get("status") or "error")
            HEALTH.record(source, status, result.get("error"))
            return {
                "source": source,
                "marketplace": getattr(provider, "marketplace", None),
                "status": status,
                "items": result.get("items", []),
                "error": result.get("error"),
            }

        result = provider.search(query, limit)
        status = str(getattr(result, "status", "error") or "error")
        error = getattr(result, "error", None)
        HEALTH.record(source, status, error)
        return {
            "source": getattr(result, "source", source),
            "marketplace": getattr(result, "marketplace", None),
            "status": status,
            "items": getattr(result, "items", []) or [],
            "error": error,
        }
    except Exception as exc:
        error = str(exc)
        HEALTH.record(source, "error", error)
        return {"source": source, "status": "error", "items": [], "error": error}


def search_sources(query: str, limit: int = 20, sources: list[str] | None = None) -> dict[str, Any]:
    """Search configured marketplace and feed sources concurrently."""
    default_sources = ["wildberries", "ozon", "simaland", *FEED_ADAPTERS]
    selected = list(dict.fromkeys(sources or default_sources))
    if not selected:
        return {"query": query, "count": 0, "items": [], "sources": [], "ready": False}

    max_workers = max(1, min(int(os.getenv("SOURCE_SEARCH_WORKERS", str(len(selected)))), len(selected)))
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="source") as executor:
        futures = {executor.submit(_run_source, source, query, limit): source for source in selected}
        for future in as_completed(futures):
            results.append(future.result())

    order = {source: index for index, source in enumerate(selected)}
    results.sort(key=lambda result: order.get(str(result.get("source")), len(order)))

    items: list[dict[str, Any]] = []
    for result in results:
        items.extend(result.get("items", []))

    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (str(item.get("marketplace") or ""), str(item.get("id") or item.get("product_id") or item.get("url") or ""))
        if key not in seen:
            seen.add(key)
            unique.append(item)

    unique = sorted(
        unique,
        key=lambda item: (
            item.get("price") is None,
            item.get("price") if isinstance(item.get("price"), (int, float)) else float("inf"),
            -(item.get("discount_percent") or 0),
        ),
    )

    return {
        "query": query,
        "count": len(unique[:limit]),
        "items": unique[:limit],
        "sources": results,
        "ready": any(r.get("status") == "ok" and r.get("items") for r in results),
    }
