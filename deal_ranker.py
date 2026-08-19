from __future__ import annotations

import re
from typing import Any


def _tokens(value: str) -> set[str]:
    return {x for x in re.findall(r"[\wа-яё]+", value.casefold()) if len(x) > 2}


def _text(item: dict[str, Any]) -> str:
    extra = item.get("extra") or {}
    return " ".join(str(item.get(k) or "") for k in ("title", "category")) + " " + str(extra.get("description") or "")


def score_item(item: dict[str, Any], plan: dict[str, Any]) -> float:
    score = 0.0
    title_tokens = _tokens(_text(item))
    wanted = _tokens(" ".join([str(plan.get("category") or ""), *[str(x) for x in plan.get("keywords", [])]]))
    if wanted:
        score += 35.0 * len(title_tokens & wanted) / max(1, len(wanted))

    price = item.get("price")
    max_price = plan.get("max_price")
    if isinstance(price, (int, float)):
        score += 20.0
        if isinstance(max_price, (int, float)) and max_price > 0:
            if price <= max_price:
                score += 20.0 * max(0.0, 1.0 - float(price) / max_price)
            else:
                score -= 50.0

    discount = item.get("discount_percent")
    if isinstance(discount, (int, float)):
        score += min(15.0, max(0.0, float(discount)) * 0.3)

    if item.get("available") is True:
        score += 5.0

    marketplace = str(item.get("marketplace") or "")
    if marketplace in set(plan.get("marketplaces") or []):
        score += 5.0
    return round(score, 3)


def rank_items(items: list[dict[str, Any]], plan: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (str(item.get("marketplace") or ""), str(item.get("id") or item.get("url") or ""))
        if key in seen:
            continue
        seen.add(key)
        copy = dict(item)
        copy["deal_score"] = score_item(copy, plan)
        ranked.append(copy)
    ranked.sort(key=lambda x: (-float(x.get("deal_score") or 0), x.get("price") is None, x.get("price") if isinstance(x.get("price"), (int, float)) else float("inf")))
    return ranked[:limit]
