from __future__ import annotations

import hashlib
import os
import re
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from telegram_bot import send_message
from watchlist_store import list_all, notification_sent, update_price

PARSER_BASE_URL = os.getenv("PARSER_PUBLIC_URL", "http://127.0.0.1:8010").rstrip("/")
CHECK_INTERVAL = max(60, int(os.getenv("WATCHLIST_CHECK_INTERVAL", "1800")))
TIMEOUT = max(5.0, float(os.getenv("WATCHLIST_CHECK_TIMEOUT", "20")))
NOTIFICATION_COOLDOWN = max(0, int(os.getenv("WATCHLIST_NOTIFICATION_COOLDOWN", "21600")))


def _price(item: dict[str, Any]) -> float | None:
    value = item.get("price", item.get("lowest_price"))
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None
    if isinstance(value, str):
        cleaned = value.replace("\u00a0", " ").replace("₽", "").replace("руб.", "").replace("руб", "")
        cleaned = cleaned.replace(" ", "").replace(",", ".")
        try:
            parsed = float(cleaned)
            return parsed if parsed >= 0 else None
        except ValueError:
            return None
    return None


def _url(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    raw = value.strip()
    try:
        parts = urlsplit(raw)
        if not parts.scheme or not parts.netloc:
            return raw.rstrip("/")
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))
    except ValueError:
        return raw.rstrip("/")


def _tokens(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {token for token in re.findall(r"[a-zа-яё0-9]+", value.lower()) if len(token) >= 3}


def _title_matches(watched_title: Any, offer_title: Any) -> bool:
    watched = _tokens(watched_title)
    offered = _tokens(offer_title)
    if not watched or not offered:
        return False
    overlap = len(watched & offered) / len(watched)
    return overlap >= 0.5


def _best_price(item: dict[str, Any], offers: list[dict[str, Any]]) -> float | None:
    watched_url = _url(item.get("url") or item.get("product_url"))
    exact_prices: list[float] = []
    if watched_url:
        for offer in offers:
            offer_url = _url(offer.get("url") or offer.get("product_url"))
            if offer_url == watched_url:
                price = _price(offer)
                if price is not None:
                    exact_prices.append(price)
        if exact_prices:
            return min(exact_prices)

    matched_prices = [
        price
        for offer in offers
        if _title_matches(item.get("title"), offer.get("title"))
        if (price := _price(offer)) is not None
    ]
    return min(matched_prices) if matched_prices else None


def _search(item: dict[str, Any]) -> list[dict[str, Any]]:
    for path in ("/api/agent/search", "/api/child-search"):
        try:
            response = requests.get(
                f"{PARSER_BASE_URL}{path}",
                params={"q": item["title"], "limit": 8},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            offers = data.get("items") or data.get("confirmed") or []
            if isinstance(offers, list):
                valid = [offer for offer in offers if isinstance(offer, dict)]
                if valid:
                    return valid
        except Exception as exc:
            print(f"Watchlist search error on {path}: {exc}", flush=True)
    return []


def _event_key(item: dict[str, Any], new_price: float) -> str:
    identity = item.get("url") or item.get("product_url") or item.get("item_key") or item.get("title")
    raw = f"{item.get('chat_id')}|{identity}|{new_price:.2f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_once() -> int:
    checked = 0
    for item in list_all():
        try:
            offers = _search(item)
            new_price = _best_price(item, offers)
            if new_price is None:
                continue
            chat_id = int(item["chat_id"])
            item_key = str(item["item_key"])
            old_price = _price({"price": item.get("last_price")})
            update_price(chat_id, item_key, new_price)
            checked += 1
            if old_price is not None and new_price < old_price:
                event_key = _event_key(item, new_price)
                already_notified = notification_sent(event_key, chat_id, item_key, new_price, time.time(), NOTIFICATION_COOLDOWN)
                if already_notified:
                    continue
                drop = old_price - new_price
                percent = drop / old_price * 100 if old_price else 0
                send_message(
                    chat_id,
                    (
                        f"📉 Цена снизилась!\n\n{item['title']}\n"
                        f"💰 Было: {old_price:,.0f} ₽\n"
                        f"🔥 Сейчас: {new_price:,.0f} ₽\n"
                        f"⬇️ Экономия: {drop:,.0f} ₽ ({percent:.0f}%)"
                    ).replace(",", " "),
                )
        except Exception as exc:
            print(f"Watchlist check error for {item.get('item_key')}: {exc}", flush=True)
    return checked


def main() -> None:
    while True:
        try:
            checked = check_once()
            print(f"Watchlist checked: {checked}", flush=True)
        except Exception as exc:
            print(f"Watchlist checker error: {exc}", flush=True)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
