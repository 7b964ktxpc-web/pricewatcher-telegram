from __future__ import annotations

import sqlite3
from typing import Any

from watchlist_store import DB_PATH, init_db


def users(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT chat_id, COUNT(*) AS watchlist_count, MAX(updated_at) AS last_activity "
            "FROM watchlist GROUP BY chat_id ORDER BY last_activity DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def user_items(chat_id: int, limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT rowid AS id, chat_id, item_key, title, url, source, last_price, updated_at "
            "FROM watchlist WHERE chat_id=? ORDER BY updated_at DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def find(query: str, limit: int = 20) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT chat_id, COUNT(*) AS watchlist_count, MAX(updated_at) AS last_activity "
            "FROM watchlist WHERE CAST(chat_id AS TEXT)=? GROUP BY chat_id LIMIT ?",
            (q, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def card(chat_id: int) -> str:
    matches = find(str(chat_id), 1)
    if not matches:
        return f"❌ Пользователь {chat_id} не найден."
    user = matches[0]
    return (
        "👤 Пользователь\n\n"
        f"🆔 Telegram ID: {user['chat_id']}\n"
        f"🔔 Watchlist: {user['watchlist_count']}\n"
        f"🕐 Последняя активность: {user['last_activity'] or 'нет данных'}"
    )


def search_text(query: str) -> str:
    matches = find(query, 20)
    if not matches:
        return f"🔎 Пользователь {query.strip() or '—'} не найден."
    lines = [f"🔎 Результаты поиска: {query.strip()}", ""]
    for user in matches:
        lines.append(
            f"• 🆔 {user['chat_id']} — 🔔 {user['watchlist_count']} — 🕐 {user['last_activity'] or '—'}"
        )
    return "\n".join(lines)
