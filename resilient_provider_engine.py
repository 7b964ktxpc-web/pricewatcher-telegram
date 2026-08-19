from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from feed_adapters import FEED_ADAPTERS
from provider_engine import search_sources as _search_sources
from source_health import HEALTH


def _run_source(source: str, query: str, limit: int) -> dict[str, Any]:
    if not HEALTH.allow(source):
        return {
            "source": source,
            "status": "cooldown",
            "items": [],
            "error": "Source temporarily paused by circuit breaker",
        }

    try:
        run = _search_sources(query, limit, [source])
        source_results = run.get("sources", [])
        if not source_results:
            result = {"source": source, "status": "error", "items": [], "error": "Provider returned no diagnostics"}
            HEALTH.record(source, "error", result["error"])
            return result

        result = source_results[0]
        status = str(result.get("status") or "error")
        HEALTH.record(source, status, result.get("error"))
        return result
    except Exception as exc:
        error = str(exc)
        HEALTH.record(source, "error", error)
        return {"source": source, "status": "error", "items": [], "error": error}


def search_sources(query: str, limit: int = 20, sources: list[str] | None = None) -> dict[str, Any]:
    """Search configured marketplace and feed sources concurrently.

    Feed adapters are part of the normal deterministic search path, not only
    the import path. This keeps /api/search useful when a permitted catalog
    feed is configured while preserving the same cooldown/retry/error
    handling as marketplace providers.
    """
    default_sources = ["wildberries", "ozon", "yandex_market", "simaland", *FEED_ADAPTERS]
    selected = list(dict.fromkeys(sources or default_sources))
    if not selected:
        return {"query": query, "count": 0, "items": [], "sources": [], "ready": False}

    max_workers = max(1, min(int(os.getenv("SOURCE_SEARCH_WORKERS", str(len(selected)))), len(selected)))
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="source") as executor:
        futures = {executor.submit(_run_source, source, query, limit): source for source in selected}
        for future in as_completed(futures):
            results.append(future.result())

    # Stable order for API consumers while retaining concurrent execution.
    order = {source: index for index, source in enumerate(selected)}
    results.sort(key=lambda result: order.get(str(result.get("source")), len(order)))

    items: list[dict[str, Any]] = []
    for result in results:
        items.extend(result.get("items", []))

    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (str(item.get("marketplace") or ""), str(item.get("id") or item.get("url") or ""))
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return {
        "query": query,
        "count": len(unique[:limit]),
        "items": unique[:limit],
        "sources": results,
        "ready": any(r.get("status") == "ok" and r.get("items") for r in results),
    }
