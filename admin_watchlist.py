from __future__ import annotations

import sqlite3
from typing import Any

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


def remove(item_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM watchlist WHERE rowid = ?", (item_id,))
        conn.commit()
        return cursor.rowcount > 0
