from __future__ import annotations

from typing import Any

from provider_engine import search_sources as _search_sources
from source_health import HEALTH


def search_sources(query: str, limit: int = 20, sources: list[str] | None = None) -> dict[str, Any]:
    """Run providers through the shared circuit breaker and preserve source diagnostics."""
    selected = sources or ["wildberries", "ozon", "yandex_market", "simaland"]
    results: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    for source in dict.fromkeys(selected):
        if not HEALTH.allow(source):
            results.append({
                "source": source,
                "status": "cooldown",
                "items": [],
                "error": "Source temporarily paused by circuit breaker",
            })
            continue

        run = _search_sources(query, limit, [source])
        source_results = run.get("sources", [])
        if not source_results:
            result = {"source": source, "status": "error", "items": [], "error": "Provider returned no diagnostics"}
            results.append(result)
            HEALTH.record(source, "error", result["error"])
            continue

        result = source_results[0]
        results.append(result)
        status = str(result.get("status") or "error")
        HEALTH.record(source, status, result.get("error"))
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
