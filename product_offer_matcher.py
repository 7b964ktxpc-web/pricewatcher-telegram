from __future__ import annotations

from typing import Any

from product_identity import identity, match_score


def group_offers(items: list[dict[str, Any]], threshold: float = 0.72) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item in items:
        ident = identity(item.get("title") or "", item)
        best_group = None
        best_score = 0.0
        for group in groups:
            score = match_score(ident, group["identity"])
            if score > best_score:
                best_score, best_group = score, group
        if best_group is None or best_score < threshold:
            groups.append({
                "match_group": f"g{len(groups) + 1}",
                "representative_title": item.get("title") or "",
                "identity": ident,
                "offers": [dict(item, match_score=1.0)],
            })
        else:
            best_group["offers"].append(dict(item, match_score=best_score))

    result: list[dict[str, Any]] = []
    for group in groups:
        offers = group["offers"]
        priced = [x for x in offers if isinstance(x.get("price"), (int, float))]
        priced.sort(key=lambda x: float(x["price"]))
        best = priced[0] if priced else offers[0]
        result.append({
            "match_group": group["match_group"],
            "representative_title": group["representative_title"],
            "identity": group["identity"],
            "offer_count": len(offers),
            "lowest_price": best.get("price"),
            "best_offer": best,
            "offers": offers,
        })
    result.sort(key=lambda x: float(x["lowest_price"]) if isinstance(x["lowest_price"], (int, float)) else float("inf"))
    return result
