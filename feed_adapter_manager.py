from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from feed_adapters import FEED_ADAPTERS


@dataclass(frozen=True)
class FeedProbe:
    name: str
    adapter: str
    configured: bool
    status: str
    format: str | None = None
    error: str | None = None


def _format_from_content_type(content_type: str) -> str | None:
    value = content_type.casefold()
    if "json" in value:
        return "json"
    if any(token in value for token in ("xml", "rss", "atom")):
        return "xml"
    return None


def _probe(name: str, adapter: Any) -> FeedProbe:
    if not adapter.configured():
        return FeedProbe(name, adapter.name, False, "not_configured")

    # Reuse the adapter's own public-feed request/parsing path. A successful
    # zero-result search still proves that the feed is reachable and parseable.
    try:
        result = adapter.search("__feed_manager_probe__", 1)
        status = str(result.get("status", "unknown"))
        if status == "ok":
            # FeedAdapter intentionally hides the response headers, so infer
            # the parser format from the normalized result path when possible.
            # The adapter accepts both JSON and XML/YML; expose "structured"
            # rather than guessing an exact wire format.
            return FeedProbe(name, adapter.name, True, "ready", "structured")
        return FeedProbe(name, adapter.name, True, status, error=result.get("error"))
    except Exception as exc:
        return FeedProbe(name, adapter.name, True, "error", error=str(exc))


def inspect_feeds() -> dict[str, Any]:
    workers = max(1, min(len(FEED_ADAPTERS), int(os.getenv("FEED_DISCOVERY_WORKERS", "6"))))
    results: list[FeedProbe] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="feed-adapter") as executor:
        futures = {executor.submit(_probe, name, adapter): name for name, adapter in FEED_ADAPTERS.items()}
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda x: x.name)
    return {
        "mode": "public-feed-adapters",
        "checked": len(results),
        "ready": [x.name for x in results if x.status == "ready"],
        "configured": [x.name for x in results if x.configured],
        "results": [x.__dict__ for x in results],
    }
