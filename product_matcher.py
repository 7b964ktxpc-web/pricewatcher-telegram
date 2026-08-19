from __future__ import annotations

import re
from typing import Any


def _tokens(value: str) -> set[str]:
    return {x for x in re.findall(r"[\wа-яё]+", value.casefold()) if len(x) > 2}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _signature(item: dict[str, Any]) -> tuple[str, ...]:
    extra = item.get("extra") or {}
    text = " ".join([
        str(item.get("title") or ""), str(item.get("category") or ""),
        str(extra.get("brand") or ""), str(extra.get("description") or ""),
    ])
    return tuple(sorted(_tokens(text)))


def match_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    aid, bid = str(a.get("id") or ""), str(b.get("id") or "")
    if aid and bid and aid == bid and a.get("marketplace") == b.get("marketplace"):
        return 1.0
    at, bt = _tokens(_norm(a.get("title"))), _tokens(_norm(b.get("title")))
    if not at or not bt:
        return 0.0
    title = len(at & bt) / max(1, len(at | bt))
    ae, be = a.get("extra") or {}, b.get("extra") or {}
    ab, bb = _norm(ae.get("brand")), _norm(be.get("brand"))
    brand = 1.0 if ab and bb and ab == bb else 0.0
    ac, bc = _norm(a.get("category")), _norm(b.get("category"))
    category = 1.0 if ac and bc and ac == bc else 0.0
    return round(min(1.0, title * 0.75 + brand * 0.15 + category * 0.10), 4)


def group_products(items: list[dict[str, Any]], threshold: float = 0.72) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item in items:
        placed = False
        for group in groups:
            representative = group["items"][0]
            if match_score(representative, item) >= threshold:
                group["items"].append(item)
                placed = True
                break
        if not placed:
            groups.append({"items": [item]})

    result: list[dict[str, Any]] = []
    for index, group in enumerate(groups, 1):
        offers = group["items"]
        priced = [x for x in offers if isinstance(x.get("price"), (int, float))]
        cheapest = min(priced, key=lambda x: x["price"]) if priced else offers[0]
        result.append({
            "match_group": index,
            "title": cheapest.get("title"),
            "category": cheapest.get("category"),
            "offers": sorted(offers, key=lambda x: x.get("price") if isinstance(x.get("price"), (int, float)) else float("inf")),
            "offer_count": len(offers),
            "best_offer": cheapest,
            "lowest_price": cheapest.get("price"),
        })
    result.sort(key=lambda x: x.get("lowest_price") if isinstance(x.get("lowest_price"), (int, float)) else float("inf"))
    return result
