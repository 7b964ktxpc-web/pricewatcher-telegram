from __future__ import annotations

import os
import sqlite3
import time
from typing import Any

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "").strip()
ADMIN_USER_IDS = {int(x.strip()) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip().lstrip("-").isdigit()}
DB_PATH = os.getenv("WATCHLIST_DB_PATH") or os.getenv("ADMIN_DB_PATH") or "/app/data/watchlist.sqlite3"
PARSER_BASE_URL = os.getenv("PARSER_PUBLIC_URL", "http://marketplace-parser:8010").rstrip("/")
TIMEOUT = max(5.0, float(os.getenv("ADMIN_BOT_TIMEOUT", "15")))


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
    return {"inline_keyboard": [[{"text": "📊 Статистика", "callback_data": "stats"}, {"text": "🩺 Система", "callback_data": "health"}], [{"text": "🔔 Watchlist", "callback_data": "watchlist"}, {"text": "🔎 Проверка поиска", "callback_data": "search"}]]}


def send_message(chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    _api("sendMessage", payload)


def _db_stats() -> dict[str, int]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            watchlist = int(conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]) if _table_exists(conn, "watchlist") else 0
            users = int(conn.execute("SELECT COUNT(DISTINCT chat_id) FROM watchlist").fetchone()[0]) if _table_exists(conn, "watchlist") else 0
            notifications = int(conn.execute("SELECT COUNT(*) FROM watchlist_notifications").fetchone()[0]) if _table_exists(conn, "watchlist_notifications") else 0
        return {"users_with_watchlist": users, "watchlist": watchlist, "notifications": notifications}
    except sqlite3.Error:
        return {"users_with_watchlist": 0, "watchlist": 0, "notifications": 0}


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


def stats_text() -> str:
    stats = _db_stats()
    return ("📊 Админ-статистика\n\n"
            f"👥 Пользователей с Watchlist: {stats['users_with_watchlist']}\n"
            f"🔔 Товаров под наблюдением: {stats['watchlist']}\n"
            f"📉 Сохранённых price-drop событий: {stats['notifications']}")


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


def _show_watchlist(chat_id: int) -> None:
    stats = _db_stats()
    send_message(chat_id, f"🔔 Watchlist\n\nТоваров: {stats['watchlist']}\nPrice-drop событий: {stats['notifications']}", menu_keyboard())


def _handle_callback(chat_id: int, user_id: int, data: str) -> None:
    if not is_admin(user_id):
        return
    if data == "stats":
        send_message(chat_id, stats_text(), menu_keyboard())
    elif data == "health":
        send_message(chat_id, health_text(), menu_keyboard())
    elif data == "watchlist":
        _show_watchlist(chat_id)
    elif data == "search":
        send_message(chat_id, _search_check(), menu_keyboard())


def handle_text(chat_id: int, user_id: int, text: str) -> None:
    if not is_admin(user_id):
        return
    command = text.strip().lower()
    if command in {"/start", "/admin", "/menu"}:
        send_message(chat_id, "🔐 Панель администратора\n\nДоступ разрешён.", menu_keyboard())
    elif command == "/stats":
        send_message(chat_id, stats_text(), menu_keyboard())
    elif command in {"/health", "/system"}:
        send_message(chat_id, health_text(), menu_keyboard())
    elif command == "/watchlist":
        _show_watchlist(chat_id)
    elif command == "/search":
        send_message(chat_id, _search_check(), menu_keyboard())
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


def main() -> None:
    validate_startup()
    offset = None
    while True:
        try:
            offset = run_once(offset)
        except KeyboardInterrupt:
            break
        except requests.RequestException as exc:
            print(f"Admin Telegram network error: {exc}", flush=True)
            time.sleep(5)
        except Exception as exc:
            print(f"Admin Telegram bot error: {exc}", flush=True)
            time.sleep(5)
        time.sleep(0.2)


if __name__ == "__main__":
    main()
