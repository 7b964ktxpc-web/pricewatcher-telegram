from __future__ import annotations

import sqlite3
from typing import Any

from watchlist_store import DB_PATH, init_db


def list_notifications(limit: int = 20, min_drop_amount: float = 0.0, min_drop_percent: float = 0.0) -> list[dict[str, Any]]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT n.event_key, n.chat_id, n.item_key, n.price, n.notified_at,
                   w.title, w.url, w.source,
                   previous.price AS previous_price
            FROM watchlist_notifications AS n
            LEFT JOIN watchlist AS w
              ON w.chat_id = n.chat_id AND w.item_key = n.item_key
            LEFT JOIN watchlist_price_history AS previous
              ON previous.id = (
                   SELECT MAX(h.id)
                   FROM watchlist_price_history AS h
                   WHERE h.chat_id = n.chat_id
                     AND h.item_key = n.item_key
                     AND h.price > n.price
               )
            ORDER BY n.notified_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        old = item.get("previous_price")
        new = item.get("price")
        if old is None or new is None or float(old) <= 0 or float(new) >= float(old):
            item["drop_amount"] = 0.0
            item["drop_percent"] = 0.0
        else:
            drop = float(old) - float(new)
            item["drop_amount"] = drop
            item["drop_percent"] = drop / float(old) * 100
        if item["drop_amount"] >= min_drop_amount and item["drop_percent"] >= min_drop_percent:
            result.append(item)
    return result


def format_notification(item: dict[str, Any]) -> str:
    old = item.get("previous_price")
    new = item.get("price")
    old_text = f"{float(old):,.0f} ₽".replace(",", " ") if old is not None else "—"
    new_text = f"{float(new):,.0f} ₽".replace(",", " ") if new is not None else "—"
    drop = f"{float(item.get('drop_amount', 0)):,.0f} ₽".replace(",", " ")
    percent = float(item.get("drop_percent", 0))
    return (
        f"📉 {item.get('title') or 'Товар'}\n"
        f"👤 {item.get('chat_id')}\n"
        f"💰 {old_text} → {new_text}\n"
        f"🔥 Экономия: {drop} ({percent:.1f}%)\n"
        f"📦 {item.get('source') or 'источник не указан'}\n"
        f"🔗 {item.get('url') or 'ссылка отсутствует'}"
    )
