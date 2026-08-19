import time

from telegram_bot import enabled, run_once


def main() -> None:
    if not enabled():
        raise SystemExit("Set TELEGRAM_BOT_TOKEN before starting the bot")
    offset = None
    while True:
        try:
            offset = run_once(offset)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"Telegram bot error: {exc}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
