from __future__ import annotations

import sqlite3
from typing import Any

from price_verifier import verify_url
from watchlist_store import DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def items(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT rowid AS id, chat_id, title, url, last_price, source, updated_at "
            "FROM watchlist ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get(item_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT rowid AS id, chat_id, title, url, last_price, source, updated_at "
            "FROM watchlist WHERE rowid = ?", (item_id,)
        ).fetchone()
    return dict(row) if row else None


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
    return {"ok": True, "item": item, "verification": result}
