from __future__ import annotations

import os
import re
from collections import defaultdict, deque
from typing import Any

import requests

from agent_router import build_plan
from conversation_agent import chat as ai_chat

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PARSER_BASE_URL = os.getenv("PARSER_PUBLIC_URL", "http://127.0.0.1:8010").rstrip("/")
MAX_HISTORY = int(os.getenv("TELEGRAM_HISTORY_SIZE", "12"))
TIMEOUT = float(os.getenv("TELEGRAM_TIMEOUT", "20"))
_history: dict[int, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))


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
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    _api("sendMessage", payload)


def menu_keyboard() -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": "🔎 Найти дешевле", "callback_data": "search"}, {"text": "📸 По фото", "callback_data": "photo"}], [{"text": "💬 Просто поговорить", "callback_data": "chat"}, {"text": "ℹ️ Помощь", "callback_data": "help"}]]}


def _remember(chat_id: int, role: str, text: str) -> None:
    _history[chat_id].append({"role": role, "content": text})


def _context(chat_id: int) -> list[dict[str, str]]:
    return list(_history[chat_id])


def _search(chat_id: int, query: str) -> None:
    try:
        build_plan(query)
    except Exception:
        pass
    try:
        response = requests.get(f"{PARSER_BASE_URL}/api/agent/search", params={"q": query, "limit": 8}, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except Exception:
        send_message(chat_id, "Я поняла, что нужно найти, но поиск сейчас недоступен. Попробуй ещё раз чуть позже.", menu_keyboard())
        return
    items = data.get("items") or []
    if not items:
        send_message(chat_id, "Пока не нашла подходящих вариантов. Можем изменить бюджет, размер или сам товар.", menu_keyboard())
        return
    _remember(chat_id, "assistant", f"Нашла варианты по запросу: {query}")
    send_message(chat_id, f"Нашла {len(items)} вариантов. Сначала показываю самые интересные 👇")
    for index, item in enumerate(items[:8], 1):
        title = str(item.get("title") or "Товар")
        price = item.get("price", item.get("lowest_price"))
        source = item.get("source") or item.get("marketplace") or "магазин"
        url = item.get("url") or item.get("product_url")
        price_text = f"{float(price):,.0f} ₽".replace(",", " ") if isinstance(price, (int, float)) else "цена уточняется"
        text = f"{index}. {title}\n💰 {price_text}\n🏪 {source}"
        if url:
            text += f"\n🛒 {url}"
        send_message(chat_id, text)


def _looks_like_search(text: str) -> bool:
    return bool(re.search(r"найди|поищи|подбери|купить|нужн|товар|дешевле|скидк|цена|₽|руб|размер|лет|год|мальчик|девочк", text, re.I))


def handle_text(chat_id: int, text: str) -> None:
    text = text.strip()
    if not text:
        return
    _remember(chat_id, "user", text)
    if text == "/start":
        send_message(chat_id, "Привет! 👋 Я помощник «Мама, дешевле!». Можешь просто разговаривать со мной обычными словами. Я помогу разобраться, а когда понадобится — сама поищу лучшие цены в интернете.", menu_keyboard())
        return
    if text == "/help":
        send_message(chat_id, "Просто пиши мне как человеку. Например: «Нужны кроссовки сыну 5 лет до 3000 рублей». Можно продолжать разговор и уточнять запрос.", menu_keyboard())
        return
    if _looks_like_search(text):
        _search(chat_id, "\n".join(f"{m['role']}: {m['content']}" for m in _context(chat_id)))
        return
    reply = ai_chat(_context(chat_id))
    _remember(chat_id, "assistant", reply)
    send_message(chat_id, reply, menu_keyboard())


def run_once(offset: int | None = None) -> int | None:
    if not enabled():
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    payload = {"timeout": 5, "allowed_updates": ["message", "callback_query"]}
    if offset is not None:
        payload["offset"] = offset
    updates = _api("getUpdates", payload).get("result", [])
    next_offset = offset
    for update in updates:
        next_offset = int(update["update_id"]) + 1
        callback = update.get("callback_query")
        if callback:
            chat = callback.get("message", {}).get("chat", {})
            chat_id = chat.get("id")
            _api("answerCallbackQuery", {"callback_query_id": callback["id"]})
            if chat_id:
                data = callback.get("data")
                if data == "search": send_message(chat_id, "🔎 Напиши обычными словами, что нужно найти.")
                elif data == "photo": send_message(chat_id, "📸 Пришли фото товара — следующим этапом подключим визуальный AI-поиск.")
                elif data == "chat": send_message(chat_id, "💬 Конечно. Просто пиши мне как обычному собеседнику — без команд.")
                else: send_message(chat_id, "ℹ️ Просто расскажи, что тебе нужно. Я помогу разобраться.", menu_keyboard())
            continue
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        if chat_id and message.get("text"):
            handle_text(int(chat_id), str(message["text"]))
    return next_offset
