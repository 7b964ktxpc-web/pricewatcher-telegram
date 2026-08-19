import time

import requests

from admin_bot import _api, enabled, run_once, validate_startup


def main() -> None:
    validate_startup()
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
    if not enabled():
        raise SystemExit("Set ADMIN_BOT_TOKEN and ADMIN_USER_IDS before starting admin bot")
    main()
