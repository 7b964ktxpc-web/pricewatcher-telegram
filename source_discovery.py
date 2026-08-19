from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlparse

import requests


@dataclass(frozen=True)
class DiscoveryTarget:
    source: str
    marketplace: str
    env_key: str
    kind: str = "feed"


TARGETS = (
    DiscoveryTarget("wildberries", "wildberries", "WB_FEED_URL"),
    DiscoveryTarget("ozon", "ozon", "OZON_FEED_URL"),
    DiscoveryTarget("yandex_market", "yandex_market", "YANDEX_MARKET_FEED_URL"),
    DiscoveryTarget("simaland", "simaland", "SIMALAND_FEED_URL"),
    DiscoveryTarget("detmir", "detmir", "DETMIR_FEED_URL"),
    DiscoveryTarget("akusherstvo", "akusherstvo", "AKUSHERSTVO_FEED_URL"),
    DiscoveryTarget("korablik", "korablik", "KORABLIK_FEED_URL"),
)

TIMEOUT = float(os.getenv("DISCOVERY_TIMEOUT", "5"))
USER_AGENT = os.getenv(
    "PARSER_USER_AGENT",
    "Mozilla/5.0 (compatible; MarketplaceParser/1.0; +https://github.com/7b964ktxpc-web/pricewatcher-telegram)",
)


def _configured_targets() -> list[tuple[DiscoveryTarget, str]]:
    result = []
    for target in TARGETS:
        url = os.getenv(target.env_key, "").strip()
        if url:
            result.append((target, url))
    return result


def _probe(target: DiscoveryTarget, url: str) -> dict:
    started = time.monotonic()
    parsed = urlparse(url)
    base = {
        "source": target.source,
        "marketplace": target.marketplace,
        "kind": target.kind,
        "configured": True,
        "url_host": parsed.netloc,
        "url_scheme": parsed.scheme,
    }
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {**base, "status": "invalid_url", "reachable": False, "error": "URL must be http(s) with a host"}

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/xml, application/rss+xml, application/json, text/xml, text/plain, */*"},
            timeout=TIMEOUT,
            stream=True,
            allow_redirects=True,
        )
        content_type = response.headers.get("content-type", "").lower()
        status = "ok" if response.ok else "http_error"
        return {
            **base,
            "status": status,
            "reachable": response.ok,
            "http_status": response.status_code,
            "content_type": content_type,
            "final_url_host": urlparse(response.url).netloc,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "structured_candidate": response.ok and any(x in content_type for x in ("xml", "json", "rss", "atom")),
            "error": None if response.ok else f"HTTP {response.status_code}",
        }
    except requests.RequestException as exc:
        return {
            **base,
            "status": "unreachable",
            "reachable": False,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "structured_candidate": False,
            "error": str(exc),
        }


def discover_sources() -> dict:
    configured = _configured_targets()
    results: list[dict] = []
    workers = max(1, min(len(configured), int(os.getenv("DISCOVERY_WORKERS", "6"))))
    if configured:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="source-discovery") as executor:
            futures = [executor.submit(_probe, target, url) for target, url in configured]
            for future in as_completed(futures):
                results.append(future.result())

    results.sort(key=lambda x: (not x.get("reachable", False), x["source"]))
    configured_names = {target.source for target, _ in configured}
    available = [x["source"] for x in results if x.get("reachable")]
    structured = [x["source"] for x in results if x.get("structured_candidate")]
    return {
        "mode": "configured-public-feeds-only",
        "checked": len(results),
        "configured": sorted(configured_names),
        "available": available,
        "structured_candidates": structured,
        "results": results,
    }
