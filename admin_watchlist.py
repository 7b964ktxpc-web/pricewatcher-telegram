from __future__ import annotations

import sqlite3
from typing import Any

from price_verifier import verify_url
from watchlist_store import DB_PATH, update_price, price_history


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _columns(conn: sqlite3.Connection) -> set[str]:
    return {str(row[1]) for row in conn.execute("PRAGMA table_info(watchlist)").fetchall()}


def items(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT rowid AS id, chat_id, title, url, last_price, source, updated_at FROM watchlist ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def get(item_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        columns = _columns(conn)
        if "item_key" in columns:
            row = conn.execute("SELECT rowid AS id, chat_id, item_key, title, url, last_price, source, updated_at FROM watchlist WHERE rowid = ?", (item_id,)).fetchone()
        else:
            row = conn.execute("SELECT rowid AS id, chat_id, title, url, last_price, source, updated_at FROM watchlist WHERE rowid = ?", (item_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item.setdefault("item_key", str(item.get("url") or item.get("title") or ""))
    return item


def remove(item_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM watchlist WHERE rowid = ?", (item_id,))
        conn.commit()
        return cursor.rowcount > 0


def verify(item_id: int) -> dict[str, Any]:
    item = get(item_id)
    if not item:
        return {"ok": False, "error": "not_found", "item_id": item_id}
    result = verify_url(item["url"], item.get("title"), item.get("last_price"))
    current = result.get("price") if isinstance(result, dict) else None
    verified = bool(result.get("verified")) if isinstance(result, dict) else False
    with _connect() as conn:
        has_item_key = "item_key" in _columns(conn)
    if verified and isinstance(current, (int, float)) and has_item_key:
        update_price(int(item["chat_id"]), str(item["item_key"]), float(current))
    return {"ok": True, "item": item, "verification": result, "history": price_history(int(item["chat_id"]), str(item["item_key"]), 10)}
