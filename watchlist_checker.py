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
            prices = [p for p in (_price(offer) for offer in offers) if p is not None]
            if not prices:
                continue
            new_price = min(prices)
            old_price = item.get("last_price")
            update_price(int(item["chat_id"]), str(item["item_key"]), new_price)
            checked += 1
            if isinstance(old_price, (int, float)) and new_price < float(old_price):
                saved = float(old_price)
                drop = saved - new_price
                percent = drop / saved * 100 if saved else 0
                send_message(
                    int(item["chat_id"]),
                    f"📉 Цена снизилась!\n\n{item['title']}\n💰 Было: {saved:,.0f} ₽\n🔥 Сейчас: {new_price:,.0f} ₽\n⬇️ Экономия: {drop:,.0f} ₽ ({percent:.0f}%)".replace(",", " "),
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
