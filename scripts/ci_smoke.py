from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    required = [
        "main.py",
        "telegram_bot.py",
        "telegram_bot_runner.py",
        "watchlist_store.py",
        "watchlist_checker.py",
        "agent_router.py",
    ]
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit(f"Missing required runtime files: {', '.join(missing)}")

    db = os.environ.get("WATCHLIST_DB_PATH", str(ROOT / ".ci-watchlist.sqlite3"))
    os.environ["WATCHLIST_DB_PATH"] = db

    # Import only after setting WATCHLIST_DB_PATH because the store may
    # resolve its database path during module import.
    from watchlist_store import init_db

    init_db()
    print("Smoke check OK")


if __name__ == "__main__":
    main()
