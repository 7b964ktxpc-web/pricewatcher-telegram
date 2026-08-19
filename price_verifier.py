from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from web_product_extractor import extract_product_page
from web_research_engine import fetch_page

PRICE_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[\s\u00a0]\d{3})*(?:[.,]\d{1,2})?|\d{2,6})(?:\s*)(?:₽|руб(?:\.|лей|ля)?|RUB)\b", re.I)

def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")

def _same_domain(a: str, b: str) -> bool:
    da, db = _domain(a), _domain(b)
    return bool(da and db and (da == db or da.endswith("." + db) or db.endswith("." + da)))

def _numbers(text: str) -> list[float]:
    values: list[float] = []
    for match in PRICE_RE.findall(text or ""):
        raw = match.replace("\u00a0", "").replace(" ", "").replace(",", ".")
        try: values.append(float(raw))
        except ValueError: continue
    return values

def verify_url(url: str, expected_title: str | None = None, expected_price: float | None = None) -> dict[str, Any]:
    page = fetch_page(url)
    if not page.get("ok"):
        return {"url": url, "verified": False, "status": page.get("status"), "error": page.get("error", "http_error"), "verification_method": "http_error"}
    products = extract_product_page(page, expected_title or "")
    product = next((item for item in products if item.get("price") is not None), products[0] if products else None)
    extracted_price = product.get("price") if product else None
    title = (product or {}).get("title") or page.get("title") or ""
    title_match = None
    if expected_title and title:
        wanted = set(re.findall(r"[\wа-яё]+", expected_title.lower()))
        got = set(re.findall(r"[\wа-яё]+", title.lower()))
        title_match = len(wanted & got) / max(1, len(wanted)) >= 0.45
    price_match = None
    if expected_price is not None and extracted_price is not None:
        price_match = abs(float(extracted_price) - float(expected_price)) < 0.01
    structured = bool(product and product.get("extra", {}).get("extraction") == "json-ld")
    verified = bool(structured and extracted_price is not None)
    if expected_title is not None: verified = verified and title_match is True
    if expected_price is not None: verified = verified and price_match is True
    if verified: status = "verified"
    elif product and extracted_price is not None: status = "needs_review"
    else: status = "discovery_only"
    # If the page disagrees with the expected offer, it is discovery-only until
    # a fresh offer can be independently verified at the current price.
    discovery_only = not verified
    return {
        "url": url, "final_url": page.get("final_url", url), "source": page.get("source"),
        "verified": verified, "verification_status": status,
        "verification_method": "json_ld_product_offer" if structured else "page_product_extraction",
        "title": title, "price": extracted_price, "expected_price": expected_price,
        "title_match": title_match, "price_match": price_match, "status": page.get("status"),
        "same_domain": _same_domain(url, page.get("final_url", url)), "discovery_only": discovery_only,
    }

def verify_candidates(items: list[dict[str, Any]], max_items: int = 8) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in items[:max_items]:
        url = item.get("url")
        if not url: continue
        result = verify_url(url, item.get("title"), item.get("price"))
        results.append({**item, **result})
    return results
