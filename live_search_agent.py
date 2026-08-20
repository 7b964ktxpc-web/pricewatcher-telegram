"""Live search orchestration for user-driven product discovery."""
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
        response = requests.get(f"{BASE_URL}{path}", params={"q": query, "limit": limit}, timeout=TIMEOUT)
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
        try:
            return float(item.get(field))
        except (TypeError, ValueError):
            continue
    return float("inf")


def _run_queries(queries: list[str], limit: int) -> tuple[list[dict[str, Any]], list[str], int]:
    endpoints = ["/api/agent/search", "/api/child-search"]
    jobs = [(path, query) for query in queries for path in endpoints]
    payloads: list[dict[str, Any]] = []
    errors: list[str] = []
    if not jobs:
        return [], errors, 0
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
            if not key:
                continue
            existing = merged.get(key)
            if existing is None or _price(item) < _price(existing):
                merged[key] = item
    results = sorted(merged.values(), key=lambda item: (_price(item), str(item.get("title") or "")))[:limit]
    return results, errors, len(payloads)


def _fallback_query(original_query: str, plan: dict[str, Any]) -> str | None:
    """Relax only the explicit price ceiling; preserve every product constraint."""
    price_fields = ("max_price", "budget", "price")
    has_price = any(plan.get(field) not in (None, "", [], {}) for field in price_fields)
    if not has_price:
        return None

    preserved_fields = (
        "query",
        "category",
        "age",
        "gender",
        "size",
        "color",
        "brand",
        "keywords",
    )
    terms: list[str] = []
    for field in preserved_fields:
        value = plan.get(field)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            terms.extend(str(item).strip() for item in value if str(item).strip())
        else:
            terms.append(str(value).strip())

    query = " ".join(dict.fromkeys(term for term in terms if term))
    return query or original_query.strip() or None


def search_live(original_query: str, limit: int = 8) -> dict[str, Any]:
    """Plan and execute live search, with one bounded price-only fallback when empty."""
    plan = build_plan(original_query)
    queries = expand_queries(plan, original_query)
    results, errors, responses = _run_queries(queries, limit)
    fallback_used = False
    fallback_query = None
    if not results:
        fallback_query = _fallback_query(original_query, plan)
        if fallback_query and fallback_query not in queries:
            fallback_used = True
            fallback_results, fallback_errors, fallback_responses = _run_queries([fallback_query], limit)
            results = fallback_results
            errors.extend(fallback_errors)
            responses += fallback_responses
    return {
        "items": results,
        "plan": plan,
        "queries": queries,
        "fallback_query": fallback_query,
        "fallback_used": fallback_used,
        "sources_attempted": len(queries) * 2 + (2 if fallback_used else 0),
        "responses": responses,
        "errors": errors[:8],
        "live": True,
    }
