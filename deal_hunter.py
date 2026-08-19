from __future__ import annotations

from typing import Any


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def deal_score(offer: dict[str, Any], competitor_prices: list[float] | None = None) -> float:
    price = _num(offer.get("price"))
    old = _num(offer.get("old_price"))
    rating = _num(offer.get("rating")) or 0.0
    reviews = _num(offer.get("feedbacks")) or _num(offer.get("reviews")) or 0.0
    if price is None or price <= 0:
        return 0.0

    discount = max(0.0, min(1.0, (old - price) / old)) if old and old > price else 0.0
    competitors = [p for p in (competitor_prices or []) if p > 0]
    market_advantage = 0.0
    if competitors:
        market = min(competitors)
        market_advantage = max(0.0, min(1.0, (market - price) / market))

    rating_score = max(0.0, min(1.0, rating / 5.0))
    review_score = min(1.0, reviews / 1000.0)
    return round(100 * (discount * 0.35 + market_advantage * 0.40 + rating_score * 0.15 + review_score * 0.10), 2)


def rank_deals(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    all_prices = [
        _num(item.get("price"))
        for group in groups
        for item in group.get("offers", [])
        if _num(item.get("price")) is not None
    ]
    result = []
    for group in groups:
        offers = group.get("offers", [])
        for offer in offers:
            others = [p for p in all_prices if p != _num(offer.get("price"))]
            offer["deal_score"] = deal_score(offer, others)
        if offers:
            group["best_deal"] = max(offers, key=lambda x: x.get("deal_score", 0))
            group["deal_score"] = group["best_deal"].get("deal_score", 0)
        result.append(group)
    return sorted(result, key=lambda x: x.get("deal_score", 0), reverse=True)
