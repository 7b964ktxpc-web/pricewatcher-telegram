from __future__ import annotations

import os
import time
from typing import Any

import requests

from telegram_bot import send_message
from watchlist_store import list_all, update_price

PARSER_BASE_URL = os.getenv("PARSER_PUBLIC_URL", "http://127.0.0.1:8010").rstrip("/")
CHECK_INTERVAL = int(os.getenv("WATCHLIST_CHECK_INTERVAL", "1800"))
TIMEOUT = float(os.getenv("WATCHLIST_CHECK_TIMEOUT", "20"))


def _price(item: dict[str, Any]) -> float | None:
    value = item.get("price", item.get("lowest_price"))
    return float(value) if isinstance(value, (int, float)) else None


def _best_price(item: dict[str, Any], offers: list[dict[str, Any]]) -> float | None:
    """Prefer the exact watched URL; only fall back to search results when it is absent."""
    watched_url = item.get("url") or item.get("product_url")
    exact_prices = [
        price
        for offer in offers
        if watched_url and (offer.get("url") or offer.get("product_url")) == watched_url
        for price in [_price(offer)]
        if price is not None
    ]
    if exact_prices:
        return min(exact_prices)

    prices = [price for offer in offers if (price := _price(offer)) is not None]
    return min(prices) if prices else None


def check_once() -> int:
    checked = 0
    for item in list_all():
        try:
            response = requests.get(
                f"{PARSER_BASE_URL}/api/child-search",
                params={"q": item["title"], "limit": 8},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            offers = data.get("confirmed") or data.get("items") or []
            if not isinstance(offers, list):
                continue
            new_price = _best_price(item, [offer for offer in offers if isinstance(offer, dict)])
            if new_price is None:
                continue

            old_price = item.get("last_price")
            update_price(int(item["chat_id"]), str(item["item_key"]), new_price)
            checked += 1

            if isinstance(old_price, (int, float)) and new_price < float(old_price):
                saved = float(old_price)
                drop = saved - new_price
                percent = drop / saved * 100 if saved else 0
                send_message(
                    int(item["chat_id"]),
                    (
                        f"📉 Цена снизилась!\n\n{item['title']}\n"
                        f"💰 Было: {saved:,.0f} ₽\n"
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
