from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


def _tokens(value: str) -> set[str]:
    return {x for x in re.findall(r"[a-zа-яё0-9]+", (value or '').lower()) if len(x) > 2}


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    sequence = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return round(0.65 * jaccard + 0.35 * sequence, 4)


def group_offers(items: list[dict[str, Any]], threshold: float = 0.68) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item in items:
        title = item.get('title') or ''
        price = item.get('price')
        best_group = None
        best_score = 0.0
        for group in groups:
            score = similarity(title, group['representative_title'])
            if score > best_score:
                best_score, best_group = score, group
        if best_group is None or best_score < threshold:
            groups.append({
                'match_group': f'g{len(groups) + 1}',
                'representative_title': title,
                'offers': [dict(item, match_score=1.0)],
            })
        else:
            best_group['offers'].append(dict(item, match_score=best_score))

    result = []
    for group in groups:
        offers = group['offers']
        priced = [x for x in offers if isinstance(x.get('price'), (int, float))]
        priced.sort(key=lambda x: float(x['price']))
        best = priced[0] if priced else offers[0]
        result.append({
            'match_group': group['match_group'],
            'representative_title': group['representative_title'],
            'offer_count': len(offers),
            'lowest_price': best.get('price'),
            'best_offer': best,
            'offers': offers,
        })
    result.sort(key=lambda x: float(x['lowest_price']) if isinstance(x['lowest_price'], (int, float)) else float('inf'))
    return result
