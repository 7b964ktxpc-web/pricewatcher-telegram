from __future__ import annotations

import html
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests

USER_AGENT = os.getenv("WEB_RESEARCH_USER_AGENT", "Mozilla/5.0 (compatible; MamaDezhevleResearch/1.0)")
TIMEOUT = float(os.getenv("WEB_RESEARCH_TIMEOUT", "10"))
MAX_PAGE_CHARS = int(os.getenv("WEB_RESEARCH_MAX_PAGE_CHARS", "30000"))
MAX_RAW_HTML_CHARS = int(os.getenv("WEB_RESEARCH_MAX_RAW_HTML_CHARS", "60000"))
SEARCH_ENGINES = {
    "duckduckgo": "https://html.duckduckgo.com/html/?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
}
TRUSTED_DEAL_DOMAINS = {"pepper.ru", "pepper.com"}
MARKETPLACE_DOMAINS = {
    "wildberries.ru": "wildberries", "ozon.ru": "ozon", "market.yandex.ru": "yandex_market",
    "sima-land.ru": "simaland", "detmir.ru": "detmir", "akusherstvo.ru": "akusherstvo", "korablik.ru": "korablik",
}


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5"}


def _clean_text(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _unwrap_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            return unquote(target)
    return url


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _source_for(url: str) -> str:
    domain = _domain(url)
    for known, source in MARKETPLACE_DOMAINS.items():
        if domain == known or domain.endswith("." + known):
            return source
    if domain in TRUSTED_DEAL_DOMAINS or domain.endswith(".pepper.ru"):
        return "pepper"
    return domain


def search_engine(query: str, engine: str = "duckduckgo", limit: int = 10) -> list[dict[str, Any]]:
    template = SEARCH_ENGINES.get(engine)
    if not template:
        return []
    try:
        r = requests.get(template.format(query=requests.utils.quote(query)), headers=_headers(), timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as exc:
        return [{"engine": engine, "query": query, "error": str(exc)}]
    found: list[dict[str, Any]] = []
    if engine == "duckduckgo":
        pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
    else:
        pattern = re.compile(r'<li[^>]*class="b_algo"[\s\S]*?<h2>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I)
    for url, title in pattern.findall(r.text):
        url = _unwrap_url(html.unescape(url))
        title = _clean_text(title)
        if url.startswith("http") and title:
            found.append({"engine": engine, "query": query, "title": title, "url": url, "source": _source_for(url)})
    return found[:limit]


def _source_priority(source: str) -> int:
    return {"pepper": 0, "ozon": 1, "wildberries": 1, "yandex_market": 1, "simaland": 2, "detmir": 2, "akusherstvo": 2, "korablik": 2}.get(source, 3)


def _extract_requested_domains(queries: list[str]) -> set[str]:
    domains: set[str] = set()
    for query in queries:
        for domain in re.findall(r"(?:site:|domain:)([a-z0-9.-]+)", query, re.I):
            domains.add(domain.lower().removeprefix("www."))
    return domains


def discover(query: str, limit: int = 8) -> dict[str, Any]:
    queries = [query, f"{query} купить цена", f"{query} скидка акция", f"{query} site:pepper.ru"]
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    engines = list(SEARCH_ENGINES)
    jobs = [(q, engine) for q in queries for engine in engines]
    with ThreadPoolExecutor(max_workers=min(8, len(jobs)), thread_name_prefix="web-search") as executor:
        futures = [executor.submit(search_engine, q, engine, limit) for q, engine in jobs]
        for future in as_completed(futures):
            for item in future.result():
                (errors if item.get("error") else results).append(item)

    dedup: dict[str, dict[str, Any]] = {}
    for item in results:
        dedup.setdefault(item["url"].split("#", 1)[0], item)
    unique = list(dedup.values())

    # Do not let a few high-ranking sources consume the complete result budget.
    # Targeted site: queries are therefore represented first, then the remaining
    # slots are filled by the best generic results.
    requested_domains = _extract_requested_domains(queries)
    selected: list[dict[str, Any]] = []
    selected_urls: set[str] = set()
    per_source_cap = max(1, min(2, limit // 4 or 1))

    def domain_matches(item: dict[str, Any], domain: str) -> bool:
        current = _domain(item.get("url", ""))
        return current == domain or current.endswith("." + domain) or domain.endswith("." + current)

    targeted = [item for item in unique if any(domain_matches(item, d) for d in requested_domains)]
    targeted.sort(key=lambda x: (_source_priority(x.get("source", "")), x.get("title", "").lower()))
    counts: dict[str, int] = {}
    for item in targeted:
        source = item.get("source", "web")
        if counts.get(source, 0) >= per_source_cap or item["url"] in selected_urls:
            continue
        selected.append(item)
        selected_urls.add(item["url"])
        counts[source] = counts.get(source, 0) + 1
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        fallback = [item for item in unique if item["url"] not in selected_urls]
        fallback.sort(key=lambda x: (_source_priority(x.get("source", "")), x.get("title", "").lower()))
        selected.extend(fallback[: limit - len(selected)])

    return {"query": query, "count": len(selected), "items": selected[:max(1, limit)], "queries": queries, "engines": engines, "errors": errors, "source_counts": counts}


def fetch_page(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"url": url, "ok": False, "error": "invalid_url"}
    try:
        r = requests.get(url, headers=_headers(), timeout=TIMEOUT, allow_redirects=True)
        content_type = r.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return {"url": url, "final_url": r.url, "ok": r.ok, "status": r.status_code, "content_type": content_type, "text": ""}
        raw_html = r.text[:MAX_RAW_HTML_CHARS]
        return {"url": url, "final_url": r.url, "ok": r.ok, "status": r.status_code, "content_type": content_type,
                "source": _source_for(r.url), "title": _page_title(raw_html), "text": _clean_text(raw_html)[:MAX_PAGE_CHARS], "raw_html": raw_html}
    except requests.RequestException as exc:
        return {"url": url, "ok": False, "error": str(exc), "source": _source_for(url)}


def _page_title(raw: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
    return _clean_text(m.group(1)) if m else ""


def research(query: str, limit: int = 8, fetch_pages: bool = True) -> dict[str, Any]:
    discovered = discover(query, limit)
    if not fetch_pages or not discovered["items"]:
        return discovered
    with ThreadPoolExecutor(max_workers=min(6, len(discovered["items"])), thread_name_prefix="web-fetch") as executor:
        futures = [executor.submit(fetch_page, item["url"]) for item in discovered["items"]]
        pages = [f.result() for f in as_completed(futures)]
    return {**discovered, "pages": pages}
