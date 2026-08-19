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
    "🔎 <b>Найти дешевле</b> — пришли товар или ссылку, а я попробую найти более выгодные варианты.\n"
    "🔔 <b>Мои товары</b> — здесь будут товары, за которыми я слежу.\n"
    "💬 <b>Просто поговорить</b> — можно уточнить запрос обычными словами.\n\n"
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
    return {"inline_keyboard": [[{"text": "🔎 Найти товар", "callback_data": "search"}, {"text": "📸 По фото", "callback_data": "photo"}], [{"text": "🔎 Найти дешевле", "callback_data": "cheaper_menu"}, {"text": "🔔 Мои товары", "callback_data": "watchlist"}], [{"text": "💬 Просто поговорить", "callback_data": "chat"}, {"text": "ℹ️ Помощь", "callback_data": "help"}]]}


def back_keyboard() -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": "🏠 Главное меню", "callback_data": "home"}]]}


def deal_keyboard(item: dict[str, Any], index: int) -> dict[str, Any]:
    rows: list[list[dict[str, Any]]] = []
    url = item.get("url") or item.get("product_url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        rows.append([{"text": "🛒 Купить", "url": url}])
    rows.append([{"text": "💰 Найти дешевле", "callback_data": f"cheaper:{index}"}, {"text": "🔄 Проверить", "callback_data": f"refresh:{index}"}])
    rows.append([{"text": "🔔 Следить", "callback_data": f"watch:{index}"}])
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
        send_message(chat_id, "🔔 <b>Здесь пока пусто</b>\n\nНайди товар и нажми «🔔 Следить». Я сообщу, когда цена заметно снизится.", menu_keyboard())
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
        print(f"Telegram search unavailable: {'; '.join(errors)}", flush=True)
        send_message(chat_id, "😔 <b>Поиск сейчас недоступен</b>\n\nПопробуй ещё раз немного позже.", menu_keyboard())
        return
    items = _extract_search_items(data)
    if not items:
        send_message(chat_id, "🔎 <b>Подходящих вариантов пока не нашла</b>\n\nПопробуй изменить бюджет, размер или описание товара.", menu_keyboard())
        return
    _last_results[chat_id] = items[:8]
    _remember(chat_id, "assistant", f"Нашла варианты по запросу: {query}")
    send_message(chat_id, f"🎉 <b>Нашла {len(_last_results[chat_id])} вариантов</b>\n\nСначала показываю наиболее подходящие 👇")
    for index, item in enumerate(_last_results[chat_id], 1):
        title = str(item.get("title") or "Товар")
        price = item.get("lowest_price", item.get("price"))
        source = item.get("source") or item.get("marketplace") or "магазин"
        text = f"<b>{index}. {title}</b>\n💰 <b>{_format_price(price)}</b>\n🏪 {source}"
        if item.get("old_price") and isinstance(item.get("old_price"), (int, float)):
            text += f"\n🏷 Было: {_format_price(item['old_price'])}"
        if item.get("offer_count"):
            text += f"\n📊 Предложений: {item['offer_count']}"
        send_message(chat_id, text, deal_keyboard(item, index - 1))
    send_message(chat_id, "Можно купить, поискать дешевле или включить 🔔 отслеживание.", menu_keyboard())


def _rerun_deal_action(chat_id: int, index: int, mode: str) -> None:
    results = _last_results.get(chat_id, [])
    if index < 0 or index >= len(results):
        send_message(chat_id, "Этот результат уже устарел. Давай сделаем новый поиск.", menu_keyboard())
        return
    title = str(results[index].get("title") or "товар")
    if mode == "cheaper":
        send_message(chat_id, "🔎 <b>Ищу дешевле…</b>\nСравниваю доступные предложения.")
        _search(chat_id, f"найди дешевле: {title}")
    else:
        send_message(chat_id, "🔄 <b>Проверяю цену…</b>\nИщу актуальные предложения.")
        _search(chat_id, title)


def _handle_callback(chat_id: int, data: str) -> None:
    if data in {"home", "start"}:
        send_message(chat_id, WELCOME_TEXT, menu_keyboard())
    elif data == "search":
        send_message(chat_id, "🔎 <b>Что ищем?</b>\n\nНапиши товар, размер/возраст и бюджет.\nНапример: «Зимняя куртка девочке 6 лет до 5000 ₽»", back_keyboard())
    elif data == "photo":
        send_message(chat_id, "📸 <b>Пришли фото товара</b>\n\nЯ попробую определить его и найти такой же или похожие варианты.", back_keyboard())
    elif data == "chat":
        send_message(chat_id, "💬 <b>Я слушаю</b>\n\nПиши вопрос обычными словами — помогу уточнить поиск или подобрать варианты.", back_keyboard())
    elif data == "cheaper_menu":
        send_message(chat_id, "🔎 <b>Найти дешевле</b>\n\nНапиши, какой товар хочешь купить, и я попробую найти более выгодные предложения.", back_keyboard())
    elif data == "watchlist":
        _show_watchlist(chat_id)
    elif data == "help":
        send_message(chat_id, HELP_TEXT, back_keyboard())
    elif data.startswith("cheaper:"):
        _rerun_deal_action(chat_id, int(data.split(":", 1)[1]), "cheaper")
    elif data.startswith("refresh:"):
        _rerun_deal_action(chat_id, int(data.split(":", 1)[1]), "refresh")
    elif data.startswith("watch:"):
        index = int(data.split(":", 1)[1])
        results = _last_results.get(chat_id, [])
        if 0 <= index < len(results):
            add_watch(chat_id, results[index])
            send_message(chat_id, "🔔 <b>Готово!</b>\n\nЯ буду следить за ценой этого товара и сообщу о заметном снижении.", menu_keyboard())
        else:
            send_message(chat_id, "Этот результат уже устарел. Сделай новый поиск.", menu_keyboard())
    elif data.startswith("unwatch:"):
        key = data.split(":", 1)[1]
        if remove_watch(chat_id, key):
            send_message(chat_id, "❌ Товар убран из отслеживания.", menu_keyboard())
        else:
            send_message(chat_id, "Этот товар уже не отслеживается.", menu_keyboard())
    else:
        send_message(chat_id, "Не поняла действие. Открой главное меню и попробуй ещё раз.", menu_keyboard())


def _looks_like_search(text: str) -> bool:
    return bool(re.search(r"найди|поищи|подбери|купить|нужн|товар|дешевле|скидк|цена|₽|руб|размер|лет|год|мальчик|девочк", text, re.I))
