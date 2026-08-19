from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = os.getenv("WATCHLIST_DB_PATH") or str(Path(__file__).resolve().parent / "data" / "watchlist.sqlite3")


def _connect() -> sqlite3.Connection:
    parent = os.path.dirname(DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS watchlist (chat_id INTEGER NOT NULL, item_key TEXT NOT NULL, title TEXT NOT NULL, url TEXT, source TEXT, last_price REAL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (chat_id, item_key))")
        conn.execute("CREATE TABLE IF NOT EXISTS watchlist_notifications (event_key TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, item_key TEXT NOT NULL, price REAL NOT NULL, notified_at REAL NOT NULL)")
        conn.commit()


def add(chat_id: int, item: dict[str, Any]) -> None:
    init_db()
    key = str(item.get("url") or item.get("product_id") or item.get("title") or "")
    title = str(item.get("title") or "Товар")
    url = item.get("url") or item.get("product_url")
    source = item.get("source") or item.get("marketplace")
    price = item.get("price", item.get("lowest_price"))
    with _connect() as conn:
        conn.execute("INSERT INTO watchlist(chat_id,item_key,title,url,source,last_price) VALUES(?,?,?,?,?,?) ON CONFLICT(chat_id,item_key) DO UPDATE SET title=excluded.title,url=excluded.url,source=excluded.source,last_price=excluded.last_price,updated_at=CURRENT_TIMESTAMP", (chat_id, key, title, url, source, price if isinstance(price, (int, float)) else None))
        conn.commit()


def list_for_chat(chat_id: int) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT chat_id,item_key,title,url,source,last_price,created_at,updated_at FROM watchlist WHERE chat_id=? ORDER BY updated_at DESC", (chat_id,)).fetchall()
    return [dict(row) for row in rows]


def list_all() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT chat_id,item_key,title,url,source,last_price,created_at,updated_at FROM watchlist ORDER BY updated_at ASC").fetchall()
    return [dict(row) for row in rows]


def update_price(chat_id: int, item_key: str, price: float) -> None:
    with _connect() as conn:
        conn.execute("UPDATE watchlist SET last_price=?, updated_at=CURRENT_TIMESTAMP WHERE chat_id=? AND item_key=?", (price, chat_id, item_key))
        conn.commit()


def notification_sent(event_key: str, chat_id: int, item_key: str, price: float, now: float, cooldown: int) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT notified_at FROM watchlist_notifications WHERE event_key=?", (event_key,)).fetchone()
        if row is not None and (cooldown == 0 or now - float(row["notified_at"]) < cooldown):
            return True
        conn.execute("INSERT INTO watchlist_notifications(event_key,chat_id,item_key,price,notified_at) VALUES(?,?,?,?,?) ON CONFLICT(event_key) DO UPDATE SET chat_id=excluded.chat_id,item_key=excluded.item_key,price=excluded.price,notified_at=excluded.notified_at", (event_key, chat_id, item_key, price, now))
        conn.commit()
    return False


def remove(chat_id: int, item_key: str) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM watchlist WHERE chat_id=? AND item_key=?", (chat_id, item_key))
        conn.commit()
        return cursor.rowcount > 0
