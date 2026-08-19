from __future__ import annotations

import os
from typing import Any

import requests

PARSER_BASE_URL = os.getenv("PARSER_PUBLIC_URL", "http://marketplace-parser:8010").rstrip("/")
TIMEOUT = max(5.0, float(os.getenv("ADMIN_BOT_TIMEOUT", "15")))


def _probe(path: str = "/health") -> dict[str, Any]:
    try:
        response = requests.get(f"{PARSER_BASE_URL}{path}", timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return {"ok": True, "status": data.get("status", "ok"), "data": data}
    except Exception as exc:
        return {"ok": False, "status": type(exc).__name__, "error": str(exc)}


def snapshot() -> dict[str, Any]:
    health = _probe()
    configured = {
        "Ozon": bool(os.getenv("OZON_FEED_URL")),
        "Wildberries": bool(os.getenv("WB_FEED_URL") or os.getenv("WB_API_TOKEN")),
        "Яндекс Маркет": bool(os.getenv("YANDEX_MARKET_FEED_URL") or os.getenv("YANDEX_MARKET_API_KEY")),
        "Sima-Land": bool(os.getenv("SIMALAND_FEED_URL")),
    }
    return {"parser": health, "configured": configured}


def format_text() -> str:
    data = snapshot()
    lines = ["📦 Источники", ""]
    parser = data["parser"]
    lines.append(f"{'🟢' if parser['ok'] else '🔴'} Parser API: {parser['status']}")
    lines.append("")
    for name, configured in data["configured"].items():
        lines.append(f"{'🟢' if configured else '⚪'} {name}: {'настроен' if configured else 'не настроен'}")
    return "\n".join(lines)
