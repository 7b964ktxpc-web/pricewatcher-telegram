from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


def _tokens(value: str) -> set[str]:
    return {x for x in re.findall(r"[\wа-яё]+", value.casefold()) if len(x) > 2}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _brand(item: dict[str, Any]) -> str:
    extra = item.get("extra") or {}
    return _norm(item.get("brand") or extra.get("brand"))


def match_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    aid, bid = str(a.get("id") or ""), str(b.get("id") or "")
    if aid and bid and aid == bid and a.get("marketplace") == b.get("marketplace"):
        return 1.0
    at, bt = _tokens(_norm(a.get("title"))), _tokens(_norm(b.get("title")))
    if not at or not bt:
        return 0.0
    title_overlap = len(at & bt) / max(1, len(at | bt))
    sequence = SequenceMatcher(None, _norm(a.get("title")), _norm(b.get("title"))).ratio()
    ab, bb = _brand(a), _brand(b)
    brand = 1.0 if ab and bb and ab == bb else (0.0 if ab and bb else 0.5)
    ac, bc = _norm(a.get("category")), _norm(b.get("category"))
    category = 1.0 if ac and bc and ac == bc else 0.0
    return round(min(1.0, title_overlap * 0.45 + sequence * 0.30 + brand * 0.15 + category * 0.10), 4)


def group_products(items: list[dict[str, Any]], threshold: float = 0.72) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item in items:
        best_group = None
        best_score = 0.0
        for group in groups:
            score = max(match_score(group["items"][0], offer) for offer in [item])
            if score > best_score:
                best_group, best_score = group, score
        if best_group is not None and best_score >= threshold:
            best_group["items"].append(item)
            best_group["match_score"] = max(best_group["match_score"], best_score)
        else:
            groups.append({"items": [item], "match_score": 1.0})

    result: list[dict[str, Any]] = []
    for index, group in enumerate(groups, 1):
        offers = group["items"]
        priced = [x for x in offers if isinstance(x.get("price"), (int, float))]
        cheapest = min(priced, key=lambda x: x["price"]) if priced else offers[0]
        prices = [float(x["price"]) for x in priced]
        result.append({
            "match_group": index,
            "title": cheapest.get("title"),
            "category": cheapest.get("category"),
            "offers": sorted(offers, key=lambda x: x.get("price") if isinstance(x.get("price"), (int, float)) else float("inf")),
            "offer_count": len(offers),
            "best_offer": cheapest,
            "lowest_price": cheapest.get("price"),
            "price_spread": max(prices) - min(prices) if len(prices) > 1 else 0,
            "match_score": round(group["match_score"], 4),
        })
    return sorted(result, key=lambda x: x.get("lowest_price") if isinstance(x.get("lowest_price"), (int, float)) else float("inf"))


def compare_prices(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return group_products(items)
