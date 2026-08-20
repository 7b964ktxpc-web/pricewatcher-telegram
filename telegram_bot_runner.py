import time
from typing import Any

import requests

import telegram_bot as bot
from search_context import resolve_search_query


def _download_telegram_file(file_id: str) -> tuple[bytes, str]:
    file_info = bot._api("getFile", {"file_id": file_id}).get("result") or {}
    file_path = file_info.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        raise RuntimeError("Telegram did not return photo file path")
    response = requests.get(f"https://api.telegram.org/file/bot{bot.BOT_TOKEN}/{file_path}", timeout=bot.TIMEOUT)
    response.raise_for_status()
    mime_type = "image/png" if file_path.lower().endswith(".png") else "image/jpeg"
    return response.content, mime_type


def _handle_photo(chat_id: int, photos: list[dict[str, Any]], caption: str = "") -> None:
    if not photos:
        return
    largest = max((photo for photo in photos if isinstance(photo, dict)), key=lambda photo: int(photo.get("file_size") or 0), default=None)
    if not largest or not largest.get("file_id"):
        bot.send_message(chat_id, "📸 Не удалось получить фотографию. Попробуй отправить её ещё раз.", bot.menu_keyboard())
        return
    try:
        image_bytes, mime_type = _download_telegram_file(str(largest["file_id"]))
        description = bot.describe_image(image_bytes, mime_type)
        vision_query = str(description.get("query") or "").strip()
        query = caption.strip() or vision_query
        if not query:
            raise RuntimeError("vision returned an empty query")
        bot._remember(chat_id, "user", f"Фото: {query}")
        search_query = resolve_search_query(query, bot._context(chat_id), bot._last_results.get(chat_id, []))
        if search_query != query:
            bot.send_message(chat_id, "Поняла 🙂 Уточняю предыдущий поиск по фото и проверяю новые варианты…")
        else:
            bot.send_message(chat_id, f"📸 <b>Поняла, что ищем:</b> {query}\n\n🔎 Ищу подходящие варианты…")
        bot._search(chat_id, search_query)
    except Exception as exc:
        print(f"Telegram photo search error: {exc}", flush=True)
        bot.send_message(chat_id, "📸 <b>Не смогла разобрать фото.</b>\n\nПопробуй другое фото или напиши название товара текстом.", bot.menu_keyboard())


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
                search_query = resolve_search_query(value, bot._context(chat_id), bot._last_results.get(chat_id, []))
                if search_query != value:
                    bot.send_message(chat_id, "Поняла 🙂 Уточняю предыдущий поиск и проверяю новые варианты…")
                bot._search(chat_id, search_query)
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
        caption = message.get("caption") if isinstance(message.get("caption"), str) else ""
        _handle_photo(chat_id, message.get("photo") or [], caption)

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
            try:
                bot._handle_callback(cb_chat, callback.get("data") or "")
            except Exception as exc:
                print(f"Telegram callback error: {exc}", flush=True)


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
