from __future__ import annotations

import os
import sqlite3
from typing import Any

import requests

from admin_metrics import snapshot
from admin_sources import format_text
from admin_watchlist import items as watchlist_items, remove as remove_watchlist_item

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "").strip()
ADMIN_USER_IDS = {int(x.strip()) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip().lstrip("-").isdigit()}
DB_PATH = os.getenv("WATCHLIST_DB_PATH") or os.getenv("ADMIN_DB_PATH") or "/app/data/watchlist.sqlite3"
PARSER_BASE_URL = os.getenv("PARSER_PUBLIC_URL", "http://marketplace-parser:8010").rstrip("/")
TIMEOUT = max(5.0, float(os.getenv("ADMIN_BOT_TIMEOUT", "15")))
_pending_broadcast: set[int] = set()
_pending_delete: dict[int, int] = {}


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


def watchlist_keyboard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keyboard = []
    for row in rows:
        title = str(row.get("title") or "Товар")[:28]
        keyboard.append([{"text": f"🔎 {title}", "callback_data": f"wi:{row['id']}"}])
    keyboard.append([{"text": "↩️ В меню", "callback_data": "menu"}])
    return {"inline_keyboard": keyboard}


def watch_item_keyboard(item_id: int) -> dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🗑 Удалить", "callback_data": f"wd:{item_id}"}],
        [{"text": "↩️ Назад", "callback_data": "watchlist"}],
    ]}


def delete_confirm_keyboard(item_id: int) -> dict[str, Any]:
    return {"inline_keyboard": [[
        {"text": "✅ Да, удалить", "callback_data": f"wc:{item_id}"},
        {"text": "❌ Отмена", "callback_data": f"wi:{item_id}"},
    ]]}


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


def _user_ids() -> list[int]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            if not _table_exists(conn, "watchlist"):
                return []
            return [int(row[0]) for row in conn.execute("SELECT DISTINCT chat_id FROM watchlist ORDER BY chat_id").fetchall()]
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


def watchlist_text() -> tuple[str, dict[str, Any]]:
    rows = watchlist_items(20)
    if not rows:
        return "🔔 Watchlist\n\nПока нет товаров.", menu_keyboard()
    lines = ["🔔 Watchlist\n", "Выбери товар для управления:"]
    for row in rows:
        price = row.get("last_price")
        price_text = f"{float(price):,.0f} ₽".replace(",", " ") if price is not None else "цена не указана"
        lines.append(f"• {str(row.get('title') or 'Без названия')[:60]} — {price_text}")
    return "\n".join(lines), watchlist_keyboard(rows)


def _watch_item(item_id: int) -> tuple[str, dict[str, Any]]:
    rows = [row for row in watchlist_items(100) if int(row["id"]) == item_id]
    if not rows:
        return "❌ Товар не найден или уже удалён.", menu_keyboard()
    row = rows[0]
    price = row.get("last_price")
    price_text = f"{float(price):,.0f} ₽".replace(",", " ") if price is not None else "не указана"
    text = ("🔔 Товар Watchlist\n\n"
            f"📦 {row.get('title') or 'Без названия'}\n"
            f"👤 Пользователь: {row.get('chat_id')}\n"
            f"💰 Цена: {price_text}\n"
            f"📦 Источник: {row.get('source') or 'не указан'}\n"
            f"🕐 Обновлено: {row.get('updated_at') or 'неизвестно'}\n"
            f"🔗 {row.get('url') or 'ссылка отсутствует'}")
    return text, watch_item_keyboard(item_id)


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


def _broadcast(text: str) -> str:
    user_ids = [user_id for user_id in _user_ids() if user_id not in ADMIN_USER_IDS]
    sent = failed = 0
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
        text, keyboard = watchlist_text()
        send_message(chat_id, text, keyboard)
    elif data.startswith("wi:"):
        try:
            item_id = int(data.split(":", 1)[1])
            text, keyboard = _watch_item(item_id)
            send_message(chat_id, text, keyboard)
        except ValueError:
            send_message(chat_id, "❌ Некорректный ID товара.", menu_keyboard())
    elif data.startswith("wd:"):
        try:
            item_id = int(data.split(":", 1)[1])
            _pending_delete[user_id] = item_id
            send_message(chat_id, "⚠️ Точно удалить этот товар из Watchlist?", delete_confirm_keyboard(item_id))
        except ValueError:
            send_message(chat_id, "❌ Некорректный ID товара.", menu_keyboard())
    elif data.startswith("wc:"):
        try:
            item_id = int(data.split(":", 1)[1])
            if _pending_delete.get(user_id) != item_id:
                send_message(chat_id, "❌ Подтверждение устарело.", menu_keyboard())
                return
            _pending_delete.pop(user_id, None)
            result = remove_watchlist_item(item_id)
            send_message(chat_id, "🗑 Товар удалён." if result else "❌ Товар уже отсутствует.", menu_keyboard())
        except ValueError:
            send_message(chat_id, "❌ Некорректный ID товара.", menu_keyboard())
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
        _pending_delete.pop(user_id, None)
        send_message(chat_id, "Отменено.", menu_keyboard())
        return
    if user_id in _pending_broadcast and not command.startswith("/"):
        _pending_broadcast.discard(user_id)
        send_message(chat_id, _broadcast(text), menu_keyboard())
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
        text_out, keyboard = watchlist_text()
        send_message(chat_id, text_out, keyboard)
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
