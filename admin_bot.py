from __future__ import annotations

import os
import sqlite3
from typing import Any

import requests

from admin_metrics import snapshot
from admin_sources import format_text

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "").strip()
ADMIN_USER_IDS = {int(x.strip()) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip().lstrip("-").isdigit()}
DB_PATH = os.getenv("WATCHLIST_DB_PATH") or os.getenv("ADMIN_DB_PATH") or "/app/data/watchlist.sqlite3"
PARSER_BASE_URL = os.getenv("PARSER_PUBLIC_URL", "http://marketplace-parser:8010").rstrip("/")
TIMEOUT = max(5.0, float(os.getenv("ADMIN_BOT_TIMEOUT", "15")))
_pending_broadcast: set[int] = set()


def enabled() -> bool:
    return bool(BOT_TOKEN and ADMIN_USER_IDS)


def _api(method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.post(TELEGRAM_API.format(token=BOT_TOKEN, method=method), json=payload or {}, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", "Telegram API error"))
    return data


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in ADMIN_USER_IDS


def menu_keyboard() -> dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "📊 Статистика", "callback_data": "stats"}, {"text": "🩺 Система", "callback_data": "health"}],
        [{"text": "👥 Пользователи", "callback_data": "users"}, {"text": "🔔 Watchlist", "callback_data": "watchlist"}],
        [{"text": "🔎 Поиск", "callback_data": "search"}, {"text": "📦 Источники", "callback_data": "sources"}],
        [{"text": "📢 Рассылка", "callback_data": "broadcast"}, {"text": "🔄 Обновить", "callback_data": "menu"}],
    ]}


def send_message(chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    _api("sendMessage", payload)


def _db_stats() -> dict[str, int]:
    try:
        stats = snapshot()
        return {"users_with_watchlist": stats["users"], "watchlist": stats["watchlist"], "notifications": stats["notifications"]}
    except (sqlite3.Error, OSError):
        return {"users_with_watchlist": 0, "watchlist": 0, "notifications": 0}


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


def _watchlist_rows(limit: int = 10) -> list[tuple[Any, ...]]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            if not _table_exists(conn, "watchlist"):
                return []
            return conn.execute("SELECT chat_id,title,last_price,source FROM watchlist ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    except sqlite3.Error:
        return []


def _user_ids() -> list[int]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            if not _table_exists(conn, "watchlist"):
                return []
            rows = conn.execute("SELECT DISTINCT chat_id FROM watchlist ORDER BY chat_id").fetchall()
            return [int(row[0]) for row in rows]
    except sqlite3.Error:
        return []


def stats_text() -> str:
    stats = _db_stats()
    return ("📊 Админ-статистика\n\n"
            f"👥 Пользователей с Watchlist: {stats['users_with_watchlist']}\n"
            f"🔔 Товаров под наблюдением: {stats['watchlist']}\n"
            f"📉 Price-drop событий: {stats['notifications']}")


def users_text() -> str:
    users = _user_ids()
    if not users:
        return "👥 Пользователи\n\nПользователей с Watchlist пока нет."
    preview = "\n".join(f"• `{user_id}`" for user_id in users[:20])
    suffix = f"\n\nИ ещё: {len(users) - 20}" if len(users) > 20 else ""
    return f"👥 Пользователи с Watchlist: {len(users)}\n\n{preview}{suffix}"


def watchlist_text() -> str:
    rows = _watchlist_rows()
    if not rows:
        return "🔔 Watchlist\n\nПока нет товаров."
    lines = ["🔔 Последние товары Watchlist", ""]
    for chat_id, title, price, source in rows:
        price_text = f"{float(price):,.0f} ₽".replace(",", " ") if price is not None else "цена не указана"
        lines.append(f"• {title}\n  👤 {chat_id} · 💰 {price_text} · {source or 'источник неизвестен'}")
    return "\n".join(lines)


def sources_text() -> str:
    return format_text()


def health_text() -> str:
    lines = ["🩺 Состояние системы"]
    try:
        response = requests.get(f"{PARSER_BASE_URL}/health", timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        lines.append(f"🟢 Parser API: {data.get('status', 'ok')}")
    except Exception as exc:
        lines.append(f"🔴 Parser API: {type(exc).__name__}")
    stats = _db_stats()
    lines.append(f"💾 Watchlist DB: {stats['watchlist']} товаров")
    lines.append(f"📉 Notification DB: {stats['notifications']} событий")
    lines.append(f"🤖 Admin bot: {'🟢 configured' if enabled() else '🔴 not configured'}")
    return "\n".join(lines)


def _search_check() -> str:
    try:
        response = requests.get(f"{PARSER_BASE_URL}/api/agent/search", params={"q": "детская футболка мальчик 5 лет", "limit": 1}, timeout=max(TIMEOUT, 30.0))
        response.raise_for_status()
        data = response.json()
        return f"🔎 Поиск: {'🟢' if data.get('ready') or data.get('count', 0) > 0 else '🟡'}\nРезультатов: {data.get('count', 0)}"
    except Exception as exc:
        return f"🔴 Поиск недоступен: {type(exc).__name__}"


def _show_menu(chat_id: int) -> None:
    send_message(chat_id, "🔐 Панель администратора\n\nВыбери нужный раздел:", menu_keyboard())


def _broadcast(chat_id: int, text: str) -> str:
    user_ids = [user_id for user_id in _user_ids() if user_id not in ADMIN_USER_IDS]
    sent = 0
    failed = 0
    for user_id in user_ids:
        try:
            send_message(user_id, f"📢 Сообщение от «Мама, тут дешевле!»\n\n{text}")
            sent += 1
        except Exception:
            failed += 1
    return f"📢 Рассылка завершена\n\n🟢 Отправлено: {sent}\n🔴 Ошибок: {failed}"


def _handle_callback(chat_id: int, user_id: int, data: str) -> None:
    if not is_admin(user_id):
        return
    if data == "stats":
        send_message(chat_id, stats_text(), menu_keyboard())
    elif data == "health":
        send_message(chat_id, health_text(), menu_keyboard())
    elif data == "users":
        send_message(chat_id, users_text(), menu_keyboard())
    elif data == "watchlist":
        send_message(chat_id, watchlist_text(), menu_keyboard())
    elif data == "search":
        send_message(chat_id, _search_check(), menu_keyboard())
    elif data == "sources":
        send_message(chat_id, sources_text(), menu_keyboard())
    elif data == "broadcast":
        _pending_broadcast.add(user_id)
        send_message(chat_id, "📢 Напиши следующим сообщением текст рассылки.\n\nДля отмены: /cancel", menu_keyboard())
    elif data == "menu":
        _show_menu(chat_id)


def handle_text(chat_id: int, user_id: int, text: str) -> None:
    if not is_admin(user_id):
        return
    command = text.strip().lower()
    if command == "/cancel":
        _pending_broadcast.discard(user_id)
        send_message(chat_id, "Отменено.", menu_keyboard())
        return
    if user_id in _pending_broadcast and not command.startswith("/"):
        _pending_broadcast.discard(user_id)
        send_message(chat_id, _broadcast(chat_id, text), menu_keyboard())
        return
    if command in {"/start", "/admin", "/menu"}:
        _show_menu(chat_id)
    elif command == "/stats":
        send_message(chat_id, stats_text(), menu_keyboard())
    elif command in {"/health", "/system"}:
        send_message(chat_id, health_text(), menu_keyboard())
    elif command == "/users":
        send_message(chat_id, users_text(), menu_keyboard())
    elif command == "/watchlist":
        send_message(chat_id, watchlist_text(), menu_keyboard())
    elif command == "/search":
        send_message(chat_id, _search_check(), menu_keyboard())
    elif command == "/sources":
        send_message(chat_id, sources_text(), menu_keyboard())
    elif command == "/broadcast":
        _pending_broadcast.add(user_id)
        send_message(chat_id, "📢 Напиши текст рассылки следующим сообщением.\n\n/cancel — отменить", menu_keyboard())
    else:
        send_message(chat_id, "Выбери действие в панели администратора.", menu_keyboard())


def run_once(offset: int | None = None) -> int | None:
    if not enabled():
        raise RuntimeError("ADMIN_BOT_TOKEN and ADMIN_USER_IDS are required")
    payload: dict[str, Any] = {"timeout": 5, "allowed_updates": ["message", "callback_query"]}
    if offset is not None:
        payload["offset"] = offset
    updates = _api("getUpdates", payload).get("result", [])
    next_offset = offset
    for update in updates:
        next_offset = int(update["update_id"]) + 1
        callback = update.get("callback_query")
        if callback:
            message = callback.get("message", {})
            user = callback.get("from", {})
            chat_id = message.get("chat", {}).get("id")
            user_id = user.get("id")
            try:
                _api("answerCallbackQuery", {"callback_query_id": callback["id"]})
            except Exception:
                pass
            if chat_id is not None and user_id is not None:
                _handle_callback(int(chat_id), int(user_id), str(callback.get("data") or ""))
            continue
        message = update.get("message", {})
        user_id = message.get("from", {}).get("id")
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text")
        if chat_id is not None and user_id is not None and isinstance(text, str):
            handle_text(int(chat_id), int(user_id), text)
    return next_offset


def validate_startup() -> None:
    if not enabled():
        raise SystemExit("Set ADMIN_BOT_TOKEN and ADMIN_USER_IDS before starting admin bot")
    result = _api("getMe")
    bot = result.get("result", {})
    username = bot.get("username") or bot.get("first_name") or "unknown"
    print(f"Admin Telegram bot authenticated: @{username}; admins={sorted(ADMIN_USER_IDS)}", flush=True)
