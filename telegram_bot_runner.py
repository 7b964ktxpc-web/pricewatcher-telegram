import time

import requests

from telegram_bot import _api, enabled, run_once


def validate_startup() -> None:
    """Fail fast on an invalid Telegram token instead of restarting forever."""
    if not enabled():
        raise SystemExit("Set TELEGRAM_BOT_TOKEN before starting the bot")
    result = _api("getMe")
    bot = result.get("result", {})
    username = bot.get("username") or bot.get("first_name") or "unknown"
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
