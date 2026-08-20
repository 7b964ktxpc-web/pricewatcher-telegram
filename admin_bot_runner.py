import time
from typing import Any

import requests

import admin_bot as bot


def _handle_update(update: dict[str, Any]) -> None:
    callback = update.get("callback_query") or {}
    if callback:
        callback_id = callback.get("id")
        if callback_id:
            try:
                bot._api("answerCallbackQuery", {"callback_query_id": callback_id})
            except Exception:
                pass
        message = callback.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        user_id = (callback.get("from") or {}).get("id")
        if chat_id is None or not bot.is_admin(user_id):
            return
        data = callback.get("data") or ""
        if data in {"menu", "start"}:
            bot.send_message(chat_id, "🛠 <b>Админ-панель</b>", bot.menu_keyboard())
        elif data == "stats":
            bot.send_message(chat_id, bot.stats_text(), bot.menu_keyboard())
        elif data == "health":
            bot.send_message(chat_id, "🩺 Система\n\nParser: " + bot.PARSER_BASE_URL, bot.menu_keyboard())
        elif data == "users":
            bot.send_message(chat_id, *bot.users_text())
        elif data == "watchlist":
            bot.send_message(chat_id, *bot.watchlist_text())
        elif data == "sources":
            bot.send_message(chat_id, bot.format_text(), bot.menu_keyboard())
        elif data == "search":
            bot.send_message(chat_id, "🔎 Поиск выполняется через пользовательского бота.", bot.menu_keyboard())
        elif data.startswith("u:"):
            bot.send_message(chat_id, *bot._user_text(int(data.split(":", 1)[1])))
        elif data.startswith("ui:"):
            bot.send_message(chat_id, *bot._user_items_text(int(data.split(":", 1)[1])))
        elif data.startswith("wi:"):
            bot.send_message(chat_id, *bot._watch_item(int(data.split(":", 1)[1])))
        elif data.startswith("wv:"):
            item_id = int(data.split(":", 1)[1])
            bot.send_message(chat_id, bot._watch_verify_text(item_id), bot.watch_item_keyboard(item_id))
        elif data.startswith("wd:"):
            item_id = int(data.split(":", 1)[1])
            bot.send_message(chat_id, "Удалить этот товар?", bot.delete_confirm_keyboard(item_id))
        elif data.startswith("wc:"):
            item_id = int(data.split(":", 1)[1])
            bot.remove_watchlist_item(item_id)
            bot.send_message(chat_id, "🗑 Товар удалён.", bot.menu_keyboard())
        return

    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    user_id = (message.get("from") or {}).get("id")
    text = message.get("text")
    if chat_id is None or not isinstance(text, str):
        return
    if text.strip().startswith("/start"):
        if bot.is_admin(user_id):
            bot.send_message(chat_id, "🛠 <b>Админ-панель</b>", bot.menu_keyboard())
        return
    bot.handle_text(chat_id, user_id, text)


def run_once(offset: int | None) -> int | None:
    result = bot._api("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message", "callback_query"]})
    updates = result.get("result") or []
    next_offset = offset
    for update in updates:
        _handle_update(update)
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            next_offset = update_id + 1
    return next_offset


def main() -> None:
    if not bot.enabled():
        raise SystemExit("Set ADMIN_BOT_TOKEN and ADMIN_USER_IDS before starting admin bot")
    result = bot._api("getMe")
    telegram_bot = result.get("result", {})
    username = telegram_bot.get("username") or telegram_bot.get("first_name") or "unknown"
    print(f"Admin bot authenticated: @{username}", flush=True)
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


if __name__ == "__main__":
    main()
