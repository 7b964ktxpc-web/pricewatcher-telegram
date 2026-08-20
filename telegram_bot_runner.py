import time
from typing import Any

import requests

import telegram_bot as bot


def _handle_update(update: dict[str, Any]) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    text = message.get("text")
    if isinstance(text, str):
        value = text.strip()
        if value.startswith("/start"):
            bot.send_message(chat_id, bot.WELCOME_TEXT, bot.menu_keyboard())
        elif value.startswith("/help"):
            bot.send_message(chat_id, bot.HELP_TEXT, bot.menu_keyboard())
        elif value:
            bot._remember(chat_id, "user", value)
            if bot._looks_like_search(value):
                bot._search(chat_id, value)
            else:
                try:
                    reply = bot.ai_chat(value, bot._context(chat_id))
                    if isinstance(reply, str) and reply.strip():
                        bot._remember(chat_id, "assistant", reply)
                        bot.send_message(chat_id, reply, bot.menu_keyboard())
                    else:
                        bot.send_message(chat_id, "💬 Расскажи, какой товар ищем — помогу подобрать.", bot.menu_keyboard())
                except Exception:
                    bot.send_message(chat_id, "💬 Расскажи, какой товар ищем — помогу подобрать.", bot.menu_keyboard())
    elif message.get("photo"):
        bot.send_message(chat_id, "📸 Фото получено. Попробуй ещё раз с описанием товара, чтобы я точнее нашла варианты.", bot.menu_keyboard())

    callback = update.get("callback_query") or {}
    if callback:
        callback_id = callback.get("id")
        if callback_id:
            try:
                bot._api("answerCallbackQuery", {"callback_query_id": callback_id})
            except Exception:
                pass
        cb_message = callback.get("message") or {}
        cb_chat = (cb_message.get("chat") or {}).get("id")
        if cb_chat is not None:
            data = callback.get("data") or ""
            bot._handle_callback(cb_chat, data)


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


def validate_startup() -> None:
    if not bot.enabled():
        raise SystemExit("Set TELEGRAM_BOT_TOKEN before starting the bot")
    result = bot._api("getMe")
    telegram_bot = result.get("result", {})
    username = telegram_bot.get("username") or telegram_bot.get("first_name") or "unknown"
    print(f"Telegram bot authenticated: @{username}", flush=True)


def main() -> None:
    validate_startup()
    offset = None
    while True:
        try:
            offset = run_once(offset)
        except KeyboardInterrupt:
            break
        except requests.RequestException as exc:
            print(f"Telegram network error: {exc}", flush=True)
            time.sleep(5)
        except Exception as exc:
            print(f"Telegram bot error: {exc}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
