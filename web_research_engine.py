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
    "duckduckgo_lite": "https://lite.duckduckgo.com/lite/?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
}
TRUSTED_DEAL_DOMAINS = {"pepper.ru", "pepper.com"}
MARKETPLACE_DOMAINS = {"wildberries.ru": "wildberries", "ozon.ru": "ozon", "market.yandex.ru": "yandex_market", "sima-land.ru": "simaland", "detmir.ru": "detmir", "akusherstvo.ru": "akusherstvo", "korablik.ru": "korablik"}


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5"}


def _clean_text(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", value, flags=re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _unwrap_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            return unquote(target)
    return html.unescape(url)


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


def extract_price(text: str) -> float | None:
    if not text:
        return None
    normalized = text.replace("\xa0", " ").replace("₽", " руб ").replace("р.", " руб ")
    patterns = [
        r"(?:цена|стоимость|от|всего)\s*[:\-]?\s*(\d{1,6}(?:[\s.]\d{3})?(?:[,.]\d{1,2})?)\s*(?:руб(?:лей|ля)?|р)\b",
        r"(\d{1,6}(?:[\s.]\d{3})?(?:[,.]\d{1,2})?)\s*(?:руб(?:лей|ля)?|р)\b",
        r"(?:руб|₽)\s*(\d{1,6}(?:[\s.]\d{3})?(?:[,.]\d{1,2})?)",
    ]
    values: list[float] = []
    for pattern in patterns:
        for match in re.finditer(pattern, normalized, re.I):
            raw = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
            try:
                value = float(raw)
            except ValueError:
                continue
            if 10 <= value <= 10_000_000:
                values.append(value)
    return min(values) if values else None


def _parse_search_html(raw: str, engine: str, query: str, limit: int) -> list[dict[str, Any]]:
    patterns = []
    if engine in {"duckduckgo", "duckduckgo_lite"}:
        patterns = [
            r'<a[^>]*class=["\'][^"\']*result__a[^"\']*["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            r'<a[^>]*class=["\'][^"\']*result-link[^"\']*["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        ]
    else:
        patterns = [
            r'<li[^>]*class=["\'][^"\']*b_algo[^"\']*["\'][^>]*>[\s\S]*?<h2[^>]*>\s*<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            r'<h2[^>]*>\s*<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        ]
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern in patterns:
        for url, title in re.findall(pattern, raw, flags=re.I | re.S):
            url, title = _unwrap_url(url), _clean_text(title)
            if not url.startswith("http") or not title or url in seen:
                continue
            seen.add(url)
            found.append({"engine": engine, "query": query, "title": title, "url": url, "source": _source_for(url), "price": extract_price(title)})
            if len(found) >= limit:
                return found
    return found


def search_engine(query: str, engine: str = "duckduckgo", limit: int = 10) -> list[dict[str, Any]]:
    template = SEARCH_ENGINES.get(engine)
    if not template:
        return []
    try:
        r = requests.get(template.format(query=requests.utils.quote(query)), headers=_headers(), timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as exc:
        return [{"engine": engine, "query": query, "error": str(exc)}]
    return _parse_search_html(r.text, engine, query, limit)


def _source_priority(source: str) -> int:
    return {"pepper": 0, "ozon": 1, "wildberries": 1, "yandex_market": 1, "simaland": 2, "detmir": 2, "akusherstvo": 2, "korablik": 2}.get(source, 3)


def _extract_requested_domains(queries: list[str]) -> set[str]:
    return {d.lower().removeprefix("www.") for q in queries for d in re.findall(r"(?:site:|domain:)([a-z0-9.-]+)", q, re.I)}


def discover(query: str, limit: int = 8) -> dict[str, Any]:
    queries = [query, f"{query} купить цена", f"{query} скидка акция", f"{query} site:pepper.ru"]
    results, errors = [], []
    engines = list(SEARCH_ENGINES)
    jobs = [(q, e) for q in queries for e in engines]
    with ThreadPoolExecutor(max_workers=min(10, len(jobs)), thread_name_prefix="web-search") as executor:
        futures = [executor.submit(search_engine, q, e, limit) for q, e in jobs]
        for future in as_completed(futures):
            for item in future.result():
                (errors if item.get("error") else results).append(item)
    dedup: dict[str, dict[str, Any]] = {}
    for item in results:
        dedup.setdefault(item["url"].split("#", 1)[0], item)
    unique = list(dedup.values())
    requested_domains = _extract_requested_domains(queries)
    selected, selected_urls, counts = [], set(), {}
    per_source_cap = max(1, min(2, limit // 4 or 1))

    def domain_matches(item: dict[str, Any], domain: str) -> bool:
        current = _domain(item.get("url", ""))
        return current == domain or current.endswith("." + domain) or domain.endswith("." + current)

    targeted = [i for i in unique if any(domain_matches(i, d) for d in requested_domains)]
    targeted.sort(key=lambda x: (_source_priority(x.get("source", "")), x.get("title", "").lower()))
    for item in targeted:
        source = item.get("source", "web")
        if counts.get(source, 0) >= per_source_cap or item["url"] in selected_urls:
            continue
        selected.append(item); selected_urls.add(item["url"]); counts[source] = counts.get(source, 0) + 1
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        fallback = [i for i in unique if i["url"] not in selected_urls]
        fallback.sort(key=lambda x: (_source_priority(x.get("source", "")), x.get("title", "").lower()))
        selected.extend(fallback[:limit - len(selected)])
    return {"query": query, "count": len(selected), "items": selected[:max(1, limit)], "queries": queries, "engines": engines, "errors": errors, "source_counts": counts}


def _page_title(raw: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
    return _clean_text(m.group(1)) if m else ""


def _classify_page(status: int, final_url: str, content_type: str, text: str, raw_html: str) -> str:
    lower = (text + " " + raw_html[:12000]).lower()
    if status == 429:
        return "rate_limited"
    if status in {401} and ("login" in lower or "войти" in lower):
        return "auth_required"
    if status in {403, 406, 451} or any(x in lower for x in ("access denied", "доступ запрещен", "captcha", "cloudflare")):
        return "blocked"
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return "non_html"
    if len(text.strip()) < 200 and any(x in lower for x in ("enable javascript", "javascript required", "включите javascript")):
        return "dynamic_page"
    if _domain(final_url) and text:
        return "html_page"
    return "empty_page"


def fetch_page(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"url": url, "ok": False, "page_type": "invalid_url", "error": "invalid_url"}
    try:
        r = requests.get(url, headers=_headers(), timeout=TIMEOUT, allow_redirects=True)
        content_type = r.headers.get("content-type", "")
        raw_html = r.text[:MAX_RAW_HTML_CHARS] if ("text/html" in content_type or "application/xhtml" in content_type) else ""
        text = _clean_text(raw_html)[:MAX_PAGE_CHARS]
        page_type = _classify_page(r.status_code, r.url, content_type, text, raw_html)
        title = _page_title(raw_html)
        return {"url": url, "final_url": r.url, "ok": r.ok and page_type not in {"blocked", "rate_limited", "auth_required"}, "status": r.status_code, "content_type": content_type, "source": _source_for(r.url), "title": title, "text": text, "raw_html": raw_html, "price": extract_price(text) or extract_price(title), "page_type": page_type, "blocked": page_type == "blocked", "rate_limited": page_type == "rate_limited", "auth_required": page_type == "auth_required", "dynamic": page_type == "dynamic_page"}
    except requests.Timeout as exc:
        return {"url": url, "ok": False, "page_type": "timeout", "error": str(exc), "source": _source_for(url)}
    except requests.RequestException as exc:
        return {"url": url, "ok": False, "page_type": "network_error", "error": str(exc), "source": _source_for(url)}


def research(query: str, limit: int = 8, fetch_pages: bool = True) -> dict[str, Any]:
    discovered = discover(query, limit)
    if not fetch_pages or not discovered["items"]:
        return discovered
    with ThreadPoolExecutor(max_workers=min(6, len(discovered["items"])), thread_name_prefix="web-fetch") as executor:
        futures = [executor.submit(fetch_page, item["url"]) for item in discovered["items"]]
        pages = [f.result() for f in as_completed(futures)]
    return {**discovered, "pages": pages}