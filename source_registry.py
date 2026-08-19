from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SourceSpec:
    key: str
    title: str
    kind: str
    marketplace: str | None
    access: str
    enabled_by_default: bool
    env: str | None = None
    notes: str = ""


# Registry is deliberately metadata-only: it never claims that a blocked
# marketplace endpoint is an API and never requires seller credentials.
SOURCE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec("wildberries", "Wildberries", "marketplace", "wildberries", "public_endpoint_or_feed", False, "WB_FEED_URL", "Anonymous search endpoints may return 429; prefer approved feed when available."),
    SourceSpec("ozon", "Ozon", "marketplace", "ozon", "public_page_or_feed", False, "OZON_FEED_URL", "Public page access is not treated as structured API access."),
    SourceSpec("yandex_market", "Яндекс Маркет", "marketplace", "yandex_market", "public_page_or_feed", False, "YANDEX_MARKET_FEED_URL", "Use approved catalog/feed for stable structured imports."),
    SourceSpec("simaland", "Сима-Ленд", "marketplace", "simaland", "public_page_or_feed", False, "SIMALAND_FEED_URL", "Use approved catalog/feed for stable structured imports."),
    SourceSpec("detmir", "Детский мир", "children_store", None, "public_catalog_or_feed", False, "DETMIR_FEED_URL", "Candidate child-focused source; enable only after a permitted structured endpoint is configured."),
    SourceSpec("akusherstvo", "Акушерство", "children_store", None, "public_catalog_or_feed", False, "AKUSHERSTVO_FEED_URL", "Candidate child-focused source; enable only after a permitted structured endpoint is configured."),
    SourceSpec("korablik", "Кораблик", "children_store", None, "public_catalog_or_feed", False, "KORABLIK_FEED_URL", "Candidate child-focused source; enable only after a permitted structured endpoint is configured."),
)


def registry() -> dict[str, dict[str, Any]]:
    return {spec.key: asdict(spec) for spec in SOURCE_SPECS}


def configured_sources(env: dict[str, str] | None = None) -> list[str]:
    import os

    values = env or os.environ
    result: list[str] = []
    for spec in SOURCE_SPECS:
        if spec.env and values.get(spec.env, "").strip():
            result.append(spec.key)
    return result


def source_status() -> list[dict[str, Any]]:
    import os

    rows = []
    for spec in SOURCE_SPECS:
        configured = bool(spec.env and os.getenv(spec.env, "").strip())
        rows.append({**asdict(spec), "configured": configured, "runtime_enabled": configured})
    return rows
