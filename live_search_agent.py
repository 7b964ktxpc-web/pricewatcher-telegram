"""Live search orchestration for user-driven product discovery.

The agent does not require a preloaded catalog. It asks the configured parser/search
service for fresh results for several AI-expanded query variants, then merges and
ranks the returned offers.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from agent_router import build_plan, expand_queries

TIMEOUT = float(os.getenv("PARSER_SEARCH_TIMEOUT", os.getenv("TELEGRAM_TIMEOUT", "20")))
BASE_URL = os.getenv("PARSER_PUBLIC_URL", "http://127.0.0.1:8010").rstrip("/")


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("items") or payload.get("confirmed") or []
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _fetch(path: str, query: str, limit: int) -> tuple[str, dict[str, Any] | None, str | None]:
    try:
        response = requests.get(
            f"{BASE_URL}{path}",
            params={"q": query, "limit": limit},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return path, None, "invalid JSON object"
        return path, payload, None
    except Exception as exc:
        return path, None, str(exc)


def _key(item: dict[str, Any]) -> str:
    for field in ("url", "product_url", "sku", "id"):
        value = item.get(field)
        if value:
            return f"{field}:{str(value).strip().lower()}"
    title = str(item.get("title") or "").strip().lower()
    source = str(item.get("source") or item.get("marketplace") or "").strip().lower()
    return f"title:{source}:{title}"


def _price(item: dict[str, Any]) -> float:
    for field in ("lowest_price", "price", "current_price"):
        value = item.get(field)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return float("inf")


def search_live(original_query: str, limit: int = 8) -> dict[str, Any]:
    """Plan and execute a bounded, multi-query live search."""
    plan = build_plan(original_query)
    queries = expand_queries(plan, original_query)
    endpoints = ["/api/agent/search", "/api/child-search"]

    jobs = [(path, query) for query in queries for path in endpoints]
    payloads: list[dict[str, Any]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=min(6, len(jobs)), thread_name_prefix="live-search") as executor:
        futures = [executor.submit(_fetch, path, query, limit) for path, query in jobs]
        for future in as_completed(futures):
            path, payload, error = future.result()
            if payload is not None:
                payloads.append(payload)
            elif error:
                errors.append(f"{path}: {error}")

    merged: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        for item in _items(payload):
            key = _key(item)
            if key and key not in merged:
                merged[key] = item

    results = sorted(merged.values(), key=lambda item: (_price(item), str(item.get("title") or "")))[:limit]
    return {
        "items": results,
        "plan": plan,
        "queries": queries,
        "sources_attempted": len(jobs),
        "responses": len(payloads),
        "errors": errors[:8],
        "live": True,
    }
