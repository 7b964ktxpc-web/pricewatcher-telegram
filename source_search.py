from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

# Discovery-only domains. Prices must still be verified from the destination page.
SOURCES = {
    "pepper": ["pepper.ru"],
    "ozon": ["ozon.ru"],
    "wildberries": ["wildberries.ru"],
    "yandex_market": ["market.yandex.ru"],
    "sima_land": ["sima-land.ru"],
    "detmir": ["detmir.ru"],
    "korablik": ["korablik.ru"],
    "akusherstvo": ["akusherstvo.ru"],
    "kapika": ["kapika.ru"],
}


def source_queries(base_queries: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source, domains in SOURCES.items():
        for query in base_queries:
            domain = domains[0]
            result.append({
                "source": source,
                "domain": domain,
                "query": f"site:{domain} {query}",
                "url": f"https://www.google.com/search?q={quote_plus(f'site:{domain} {query}')}",
            })
    return result
