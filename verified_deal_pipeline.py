from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from price_verifier import verify_url


def verify_discovered(items: list[dict[str, Any]], limit: int = 16) -> list[dict[str, Any]]:
    candidates = [item for item in items if item.get("url")][:limit]
    if not candidates:
        return []
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(6, len(candidates)), thread_name_prefix="price-verify") as executor:
        futures = {
            executor.submit(verify_url, item["url"], item.get("title"), item.get("price")): item
            for item in candidates
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                verification = future.result()
            except Exception as exc:
                verification = {"verified": False, "error": str(exc), "discovery_only": True}
            results.append({**item, **verification})
    return results


def build_verified_deals(items: list[dict[str, Any]], limit: int = 16) -> dict[str, Any]:
    verified = verify_discovered(items, limit)
    confirmed = [item for item in verified if item.get("verified") and item.get("price") is not None]
    unverified = [item for item in verified if not item.get("verified")]
    confirmed.sort(key=lambda item: float(item["price"]))
    return {
        "count": len(confirmed),
        "items": confirmed,
        "checked": len(verified),
        "unverified": unverified,
        "ready": bool(confirmed),
    }
