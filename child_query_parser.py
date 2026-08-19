from __future__ import annotations

import re
from typing import Any

AGE_RE = re.compile(r"(?:до|для|реб[её]нк[ау]?|мальчик[ау]?|девочк[ау]?)?\s*(\d{1,2})\s*(?:лет|года|год|г\.?)(?!\w)", re.I)
SIZE_RE = re.compile(r"(?:размер|р-р|рост)\s*[:№]?\s*(\d{2,3})", re.I)
PRICE_RE = re.compile(r"(?:до|не дороже|бюджет)\s*(\d[\d\s]{1,7})(?:\s*(?:₽|руб))?", re.I)

CATEGORIES = {
    "кроссовки": "shoes", "ботинки": "shoes", "обувь": "shoes",
    "куртка": "outerwear", "комбинезон": "outerwear", "пальто": "outerwear",
    "футболка": "clothing", "штаны": "clothing", "брюки": "clothing", "платье": "clothing",
    "игрушка": "toys", "конструктор": "toys",
    "рюкзак": "bags", "костюм": "clothing", "пижама": "clothing",
}


def parse_child_query(text: str) -> dict[str, Any]:
    raw = (text or '').strip()
    lower = raw.lower()
    ages = [int(x) for x in AGE_RE.findall(lower)]
    sizes = [int(x) for x in SIZE_RE.findall(lower)]
    price_match = PRICE_RE.search(lower)
    budget = int(price_match.group(1).replace(' ', '')) if price_match else None

    gender = None
    if 'мальчик' in lower or 'мальчику' in lower or 'сын' in lower:
        gender = 'boy'
    elif 'девоч' in lower or 'доч' in lower:
        gender = 'girl'

    category = None
    for word, normalized in CATEGORIES.items():
        if word in lower:
            category = normalized
            break

    return {
        'raw_query': raw,
        'age_years': ages[0] if ages else None,
        'gender': gender,
        'size': sizes[0] if sizes else None,
        'budget_max': budget,
        'category': category,
    }


def build_search_queries(parsed: dict[str, Any]) -> list[str]:
    parts = []
    if parsed.get('gender') == 'boy': parts.append('для мальчика')
    if parsed.get('gender') == 'girl': parts.append('для девочки')
    if parsed.get('age_years') is not None: parts.append(f"{parsed['age_years']} лет")
    if parsed.get('size') is not None: parts.append(f"размер {parsed['size']}")
    if parsed.get('category'): parts.append(parsed['category'])
    base = ' '.join(parts).strip() or parsed.get('raw_query', '')
    queries = [base]
    if parsed.get('budget_max'):
        queries.append(f"{base} до {parsed['budget_max']} рублей")
    return list(dict.fromkeys(q for q in queries if q))
