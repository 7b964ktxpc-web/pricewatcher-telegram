from __future__ import annotations

import sqlite3
from typing import Any

from watchlist_store import DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def snapshot() -> dict[str, Any]:
    with _connect() as conn:
        watchlist = conn.execute("SELECT COUNT(*) AS n FROM watchlist").fetchone()["n"]
        users = conn.execute("SELECT COUNT(DISTINCT chat_id) AS n FROM watchlist").fetchone()["n"]
        notifications = conn.execute("SELECT COUNT(*) AS n FROM watchlist_notifications").fetchone()["n"]
    return {
        "users": int(users or 0),
        "watchlist": int(watchlist or 0),
        "notifications": int(notifications or 0),
    }
