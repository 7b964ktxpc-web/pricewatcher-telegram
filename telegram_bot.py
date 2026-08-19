from __future__ import annotations

import os
import re
from collections import defaultdict, deque
from typing import Any

import requests

from agent_router import build_plan
from conversation_agent import chat as ai_chat
from telegram_photo_search import describe_image
from watchlist_store import add as add_watch, init_db as init_watchlist_db, list_for_chat, remove as remove_watch

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PARSER_BASE_URL = os.getenv("PARSER_PUBLIC_URL", "http://127.0.0.1:8010").rstrip("/")
MAX_HISTORY = int(os.getenv("TELEGRAM_HISTORY_SIZE", "12"))
TIMEOUT = float(os.getenv("TELEGRAM_TIMEOUT", "20"))
_history: dict[int, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
_last_results: dict[int, list[dict[str, Any]]] = defaultdict(list)
init_watchlist_db()

WELCOME_TEXT = (
    "🛍 <b>Мама, тут дешевле! ❤️</b>\n\n"
    "Помогу найти детские товары по хорошей цене.\n\n"
    "🔎 Ищу товары и сравниваю предложения\n"
    "📸 Понимаю запрос по фото\n"
    "💰 Помогаю искать дешевле\n"
    "🔔 Могу следить за ценой и сообщить, если она заметно снизится\n\n"
    "Просто напиши, что нужно найти. Например:\n"
    "<i>«Кроссовки мальчику 5 лет до 3000 ₽»</i>"
)

HELP_TEXT = (
    "ℹ️ <b>Как пользоваться</b>\n\n"
    "🔎 <b>Найти товар</b> — напиши товар, возраст/размер и бюджет.\n"
    "📸 <b>По фото</b> — пришли фотографию товара.\n"
    "💰 <b>Найти дешевле</b> — пришли товар или ссылку, а я попробую найти более выгодные варианты.\n"
    "🔔 <b>Мои товары</b> — здесь будут товары, за которыми я слежу.\n"
    "💬 <b>Спросить AI</b> — можно уточнить запрос обычными словами.\n\n"
    "💡 Чем точнее запрос, тем лучше результат: товар + размер/возраст + бюджет."
)


def enabled() -> bool:
    return bool(BOT_TOKEN)


def _api(method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.post(TELEGRAM_API.format(token=BOT_TOKEN, method=method), json=payload or {}, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", "Telegram API error"))
    return data


def send_message(chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    _api("sendMessage", payload)


def menu_keyboard() -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": "🔎 Найти товар", "callback_data": "search"}, {"text": "📸 По фото", "callback_data": "photo"}], [{"text": "💰 Найти дешевле", "callback_data": "cheaper_menu"}, {"text": "🔔 Мои товары", "callback_data": "watchlist"}], [{"text": "💬 Спросить AI", "callback_data": "chat"}, {"text": "ℹ️ Помощь", "callback_data": "help"}]]}


def back_keyboard() -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": "🏠 Главное меню", "callback_data": "home"}]]}


def deal_keyboard(item: dict[str, Any], index: int) -> dict[str, Any]:
    rows: list[list[dict[str, Any]]] = []
    url = item.get("url") or item.get("product_url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        rows.append([{"text": "🛒 Купить", "url": url}])
    rows.append([{"text": "💰 Найти дешевле", "callback_data": f"cheaper:{index}"}, {"text": "🔄 Проверить", "callback_data": f"refresh:{index}"}])
    rows.append([{"text": "🔔 Следить за ценой", "callback_data": f"watch:{index}"}])
    return {"inline_keyboard": rows}


def _remember(chat_id: int, role: str, text: str) -> None:
    _history[chat_id].append({"role": role, "content": text})


def _context(chat_id: int) -> list[dict[str, str]]:
    return list(_history[chat_id])


def _format_price(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):,.0f} ₽".replace(",", " ")
    return "цена уточняется"


def _show_watchlist(chat_id: int) -> None:
    items = list_for_chat(chat_id)
    if not items:
        send_message(chat_id, "🔔 <b>Здесь пока пусто</b>\n\nНайди товар и нажми «🔔 Следить за ценой». Я сообщу, когда цена заметно снизится.", menu_keyboard())
        return
    send_message(chat_id, f"🔔 <b>Мои товары</b>\n\nСейчас отслеживаю: <b>{len(items)}</b>")
    for item in items:
        price = _format_price(item.get("last_price"))
        text = f"🧸 <b>{item['title']}</b>\n💰 Последняя цена: <b>{price}</b>"
        if item.get("source"):
            text += f"\n🏪 {item['source']}"
        rows = []
        if item.get("url", "").startswith(("http://", "https://")):
            rows.append([{"text": "🛒 Открыть товар", "url": item["url"]}])
        rows.append([{"text": "❌ Не следить", "callback_data": f"unwatch:{item['item_key']}"}])
        send_message(chat_id, text, {"inline_keyboard": rows})
    send_message(chat_id, "Что хочешь сделать дальше?", menu_keyboard())


def _extract_search_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = data.get("items") or data.get("confirmed") or []
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def _search(chat_id: int, query: str) -> None:
    try:
        build_plan(query)
    except Exception:
        pass
    endpoints = [("/api/agent/search", {"q": query, "limit": 8}), ("/api/child-search", {"q": query, "limit": 8})]
    data: dict[str, Any] | None = None
    errors: list[str] = []
    for path, params in endpoints:
        try:
            response = requests.get(f"{PARSER_BASE_URL}{path}", params=params, timeout=TIMEOUT)
            response.raise_for_status()
            candidate = response.json()
            if _extract_search_items(candidate):
                data = candidate
                break
            errors.append(f"{path}: no results")
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    if data is None:
        send_message(chat_id, "😔 Не получилось найти товары прямо сейчас.\n\nПопробуй изменить запрос или повторить позже.", back_keyboard())
        return
    items = _extract_search_items(data)
    _last_results[chat_id] = items
    send_message(chat_id, f"🔎 <b>Нашла варианты: {len(items)}</b>\n\nВыбери подходящий товар ниже.")
    for index, item in enumerate(items[:8]):
        title = str(item.get("title") or item.get("name") or "Товар")
        price = _format_price(item.get("price", item.get("lowest_price")))
        source = str(item.get("source") or item.get("marketplace") or "")
        text = f"🧸 <b>{title}</b>\n💰 <b>{price}</b>"
        if source:
            text += f"\n🏪 {source}"
        send_message(chat_id, text, deal_keyboard(item, index))
    send_message(chat_id, "💡 Можно нажать «🔔 Следить за ценой», чтобы я сообщил о заметном снижении.", menu_keyboard())


def _search_from_photo(chat_id: int, file_id: str) -> None:
    try:
        result = describe_image(file_id)
    except Exception:
        result = "товар для детей"
    send_message(chat_id, f"📸 <b>Попробую найти по фото</b>\n\n🔎 Определила запрос: <i>{result}</i>")
    _search(chat_id, result)


def handle_update(update: dict[str, Any]) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    text = str(message.get("text") or "").strip()
    if text in {"/start", "/menu"}:
        send_message(chat_id, WELCOME_TEXT, menu_keyboard())
        return
    if text == "/help":
        send_message(chat_id, HELP_TEXT, menu_keyboard())
        return
    if text == "/watchlist":
        _show_watchlist(chat_id)
        return
    photo = message.get("photo") or []
    if photo:
        _search_from_photo(chat_id, photo[-1].get("file_id", ""))
        return
    if text:
        _remember(chat_id, "user", text)
        _search(chat_id, text)


