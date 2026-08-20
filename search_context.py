from __future__ import annotations

import re
from typing import Any


FOLLOW_UP_PATTERNS = (
    r"\bдешевле\b",
    r"\bподешевле\b",
    r"\bдруг(ой|ие|ие варианты)\b",
    r"\bпокажи ещё\b",
    r"\bпокажи еще\b",
    r"\bдругой цвет\b",
    r"\bесть (\d{2,3})\b",
    r"\bразмер\s*\d{2,3}\b",
    r"\bдля (мальчика|девочки)\b",
    r"\bсин(ий|яя|ее)\b|\bкрасн(ый|ая|ое)\b|\bчёрн(ый|ая|ое)\b|\bчерн(ый|ая|ое)\b|\bбел(ый|ая|ое)\b",
)


def is_follow_up(text: str) -> bool:
    value = text.strip().lower()
    if not value:
        return False
    if len(value.split()) <= 7 and any(re.search(pattern, value, re.I) for pattern in FOLLOW_UP_PATTERNS):
        return True
    return value in {"покажи ещё", "покажи еще", "а дешевле?", "есть дешевле?", "а другие?", "а другой?"}


def resolve_search_query(text: str, history: list[dict[str, str]], last_results: list[dict[str, Any]]) -> str:
    value = text.strip()
    if not is_follow_up(value):
        return value

    base = ""
    for message in reversed(history):
        if message.get("role") != "user":
            continue
        candidate = str(message.get("content") or "").strip()
        if candidate and candidate != value and not candidate.startswith("Фото:"):
            base = candidate
            break

    if not base and last_results:
        base = str(last_results[0].get("title") or "").strip()

    if not base:
        return value

    return f"{base}. Уточнение пользователя: {value}"
