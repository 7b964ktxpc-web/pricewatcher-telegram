from __future__ import annotations

import os
import sqlite3
from typing import Any

import requests

from admin_metrics import snapshot
from admin_notifications import format_notification, list_notifications
from admin_sources import format_text
from admin_users import users as list_users, user_items
from admin_watchlist import items as watchlist_items, remove as remove_watchlist_item, verify as verify_watchlist_item
from watchlist_store import price_history

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
        [{"text": "📉 Уведомления", "callback_data": "notifications"}, {"text": "📦 Источники", "callback_data": "sources"}],
        [{"text": "🔎 Поиск", "callback_data": "search"}, {"text": "📢 Рассылка", "callback_data": "broadcast"}],
        [{"text": "🔄 Обновить", "callback_data": "menu"}],
    ]}


def users_keyboard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keyboard = []
    for row in rows:
        keyboard.append([{"text": f"👤 {row['chat_id']} · {row['watchlist_count']} товаров", "callback_data": f"u:{row['chat_id']}"}])
    keyboard.append([{"text": "↩️ В меню", "callback_data": "menu"}])
    return {"inline_keyboard": keyboard}


def user_keyboard(chat_id: int) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": "🔔 Товары пользователя", "callback_data": f"ui:{chat_id}"}], [{"text": "↩️ Назад", "callback_data": "users"}]]}


def user_items_keyboard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keyboard = [[{"text": f"📦 {str(row.get('title') or 'Товар')[:30]}", "callback_data": f"wi:{row['id']}"}] for row in rows]
    keyboard.append([{"text": "↩️ Пользователь", "callback_data": "users"}])
    return {"inline_keyboard": keyboard}


def watchlist_keyboard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keyboard = []
    for row in rows:
        title = str(row.get("title") or "Товар")[:28]
        keyboard.append([{"text": f"🔎 {title}", "callback_data": f"wi:{row['id']}"}])
    keyboard.append([{"text": "↩️ В меню", "callback_data": "menu"}])
    return {"inline_keyboard": keyboard}


def watch_item_keyboard(item_id: int) -> dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🔄 Проверить сейчас", "callback_data": f"wv:{item_id}"}],
        [{"text": "🗑 Удалить", "callback_data": f"wd:{item_id}"}],
        [{"text": "↩️ Назад", "callback_data": "watchlist"}],
    ]}


def delete_confirm_keyboard(item_id: int) -> dict[str, Any]:
    return {"inline_keyboard": [[
        {"text": "✅ Да, удалить", "callback_data": f"wc:{item_id}"},
        {"text": "❌ Отмена", "callback_data": f"wi:{item_id}"},
    ]]}


def notifications_keyboard() -> dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "📉 Все", "callback_data": "n:all"}],
        [{"text": "🔥 ≥10%", "callback_data": "n:p10"}, {"text": "💰 ≥500 ₽", "callback_data": "n:a500"}],
        [{"text": "↩️ В меню", "callback_data": "menu"}],
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


def _user_ids() -> list[int]:
    return [int(row["chat_id"]) for row in list_users(100)]


def stats_text() -> str:
    stats = _db_stats()
    return ("📊 Админ-статистика\n\n"
            f"👥 Пользователей с Watchlist: {stats['users_with_watchlist']}\n"
            f"🔔 Товаров под наблюдением: {stats['watchlist']}\n"
            f"📉 Price-drop событий: {stats['notifications']}")


def users_text() -> tuple[str, dict[str, Any]]:
    rows = list_users(50)
    if not rows:
        return "👥 Пользователи\n\nПользователей с Watchlist пока нет.", menu_keyboard()
    text = "👥 Пользователи\n\nВыбери пользователя:\n" + "\n".join(f"• {r['chat_id']} — {r['watchlist_count']} товаров" for r in rows)
    return text, users_keyboard(rows)


def _user_text(chat_id: int) -> tuple[str, dict[str, Any]]:
    rows = user_items(chat_id, 50)
    if not rows:
        return f"👤 Пользователь {chat_id}\n\nWatchlist пуст.", menu_keyboard()
    text = (f"👤 Пользователь\n\nTelegram ID: {chat_id}\n"
            f"🔔 Товаров: {len(rows)}\n\n"
            "Выбери действие:")
    return text, user_keyboard(chat_id)


def _user_items_text(chat_id: int) -> tuple[str, dict[str, Any]]:
    rows = user_items(chat_id, 50)
    if not rows:
        return f"🔔 Watchlist пользователя {chat_id}\n\nПусто.", user_keyboard(chat_id)
    lines = [f"🔔 Watchlist пользователя {chat_id}", ""]
    for row in rows:
        price = row.get("last_price")
        price_text = f"{float(price):,.0f} ₽".replace(",", " ") if price is not None else "цена не указана"
        lines.append(f"• {str(row.get('title') or 'Без названия')[:60]} — {price_text}")
    return "\n".join(lines), user_items_keyboard(rows)


def watchlist_text() -> tuple[str, dict[str, Any]]:
    rows = watchlist_items(20)
    if not rows:
        return "🔔 Watchlist\n\nПока нет товаров.", menu_keyboard()
    lines = ["🔔 Watchlist", "", "Выбери товар для управления:"]
    for row in rows:
        price = row.get("last_price")
        price_text = f"{float(price):,.0f} ₽".replace(",", " ") if price is not None else "цена не указана"
        lines.append(f"• {str(row.get('title') or 'Без названия')[:60]} — {price_text}")
    return "\n".join(lines), watchlist_keyboard(rows)


def _format_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return "📉 История: нет данных"
    values = [float(row["price"]) for row in history if row.get("price") is not None]
    if not values:
        return "📉 История: нет данных"
    chain = " → ".join(f"{value:,.0f} ₽".replace(",", " ") for value in values[-6:])
    change = ""
    if len(values) >= 2 and values[-2] != 0:
        pct = (values[-1] - values[-2]) / values[-2] * 100
        change = f"\n📊 Изменение: {pct:+.1f}%"
    return f"📉 История: {chain}{change}"


def _watch_item(item_id: int) -> tuple[str, dict[str, Any]]:
    rows = [row for row in watchlist_items(100) if int(row["id"]) == item_id]
    if not rows:
        return "❌ Товар не найден или уже удалён.", menu_keyboard()
    row = rows[0]
    price = row.get("last_price")
    price_text = f"{float(price):,.0f} ₽".replace(",", " ") if price is not None else "не указана"
    with sqlite3.connect(DB_PATH) as conn:
        columns = {str(r[1]) for r in conn.execute("PRAGMA table_info(watchlist)").fetchall()}
        if "item_key" in columns:
            key_row = conn.execute("SELECT item_key FROM watchlist WHERE rowid=?", (item_id,)).fetchone()
            item_key = str(key_row[0]) if key_row else str(row.get("url") or row.get("title") or "")
        else:
            item_key = str(row.get("url") or row.get("title") or "")
    history = price_history(int(row["chat_id"]), item_key, 10)
    text = ("🔔 Товар Watchlist\n\n"
            f"📦 {row.get('title') or 'Без названия'}\n"
            f"👤 Пользователь: {row.get('chat_id')}\n"
            f"💰 Цена: {price_text}\n"
            f"📦 Источник: {row.get('source') or 'не указан'}\n"
            f"🕐 Обновлено: {row.get('updated_at') or 'неизвестно'}\n"
            f"🔗 {row.get('url') or 'ссылка отсутствует'}\n\n"
            f"{_format_history(history)}")
    return text, watch_item_keyboard(item_id)


def _watch_verify_text(item_id: int) -> str:
    result = verify_watchlist_item(item_id)
    if not result.get("ok"):
        return "❌ Товар не найден или уже удалён."
    verification = result["verification"]
    item = result["item"]
    old_price = item.get("last_price")
    new_price = verification.get("price")
    status = "🟢 Подтверждена" if verification.get("verified") else ("🟡 Требует проверки" if verification.get("verification_status") == "needs_review" else "🔴 Не подтверждена")
    old_text = f"{float(old_price):,.0f} ₽".replace(",", " ") if old_price is not None else "нет"
    new_text = f"{float(new_price):,.0f} ₽".replace(",", " ") if new_price is not None else "не найдена"
    return ("🔄 Проверка цены\n\n" f"📦 {item.get('title') or 'Без названия'}\n" f"💰 Было: {old_text}\n" f"💰 Сейчас: {new_text}\n" f"🔎 Статус: {status}\n" f"🧪 Метод: {verification.get('verification_method', 'unknown')}\n" f"🔗 {verification.get('final_url') or item.get('url')}")
