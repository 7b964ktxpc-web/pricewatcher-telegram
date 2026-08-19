from __future__ import annotations

import re
from typing import Any

STOPWORDS = {
    "купить", "цена", "скидка", "акция", "детский", "детская", "детское", "для", "мальчик", "девочка",
    "ребенок", "ребёнок", "лет", "год", "года", "размер", "руб", "рублей", "новый", "новая", "новое",
}


def _norm(value: str) -> str:
    value = (value or "").lower().replace("ё", "е")
    return re.sub(r"\s+", " ", value).strip()


def identity(title: str, item: dict[str, Any] | None = None) -> dict[str, Any]:
    item = item or {}
    text = _norm(title)
    article = item.get("article") or item.get("sku") or item.get("vendor_code")
    barcode = item.get("barcode") or item.get("ean") or item.get("gtin")
    brand = _norm(str(item.get("brand") or ""))
    tokens = [t for t in re.findall(r"[a-zа-я0-9]+", text) if len(t) > 2 and t not in STOPWORDS]
    sizes = re.findall(r"(?:размер\s*)?(\d{2,3})(?:\s*(?:ru|eur))?\b", text)
    colors = re.findall(r"\b(черн\w*|бел\w*|син\w*|красн\w*|розов\w*|зелен\w*|сер\w*|желт\w*|фиолетов\w*|коричнев\w*)\b", text)
    return {"brand": brand or None, "article": str(article) if article else None, "barcode": str(barcode) if barcode else None,
            "tokens": sorted(set(tokens)), "sizes": sorted(set(sizes)), "colors": sorted(set(colors))}


def match_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    if a.get("barcode") and b.get("barcode") and a["barcode"] == b["barcode"]:
        return 1.0
    if a.get("article") and b.get("article"):
        if a["article"].lower() == b["article"].lower():
            return 0.98
        article_mismatch = True
    else:
        article_mismatch = False

    at, bt = set(a.get("tokens", [])), set(b.get("tokens", []))
    if not at or not bt:
        return 0.0
    score = len(at & bt) / len(at | bt)
    if a.get("brand") and b.get("brand") and a["brand"] == b["brand"]:
        score += 0.15
    if a.get("sizes") and b.get("sizes") and set(a["sizes"]) & set(b["sizes"]):
        score += 0.08
    if a.get("colors") and b.get("colors") and set(a["colors"]) & set(b["colors"]):
        score += 0.05
    if article_mismatch:
        score = min(score, 0.97)
    return min(1.0, round(score, 4))
