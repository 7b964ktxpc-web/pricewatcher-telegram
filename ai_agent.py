from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any

from gradio_client import Client

SPACE = os.getenv("HF_AI_SPACE", "victor/Qwen3.8-27B-free-endpoint")
HF_TOKEN = os.getenv("HF_TOKEN") or None
TIMEOUT = float(os.getenv("HF_AI_TIMEOUT", "90"))
CACHE_TTL = float(os.getenv("HF_AI_CACHE_TTL", "300"))

_client_lock = threading.Lock()
_client: QwenAgent | None = None
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class QwenAgent:
    """Provider adapter for a public Hugging Face Gradio Space."""

    def __init__(self, space: str = SPACE):
        self.space = space
        self.client = Client(space, token=HF_TOKEN, verbose=False)
        self.api = self.client.view_api(all_endpoints=True, print_info=False)

    def _endpoint(self) -> str:
        named = self.api.get("named_endpoints", {}) if isinstance(self.api, dict) else {}
        preferred = ("chat", "predict", "generate", "completion", "respond")
        for needle in preferred:
            for name in named:
                if needle in name.lower():
                    return name
        if len(named) == 1:
            return next(iter(named))
        raise RuntimeError(f"No suitable text endpoint found in {list(named)}")

    def _parameters(self, endpoint: str) -> list[dict[str, Any]]:
        return (self.api.get("named_endpoints", {}).get(endpoint, {}) or {}).get("parameters", [])

    def generate(self, prompt: str) -> str:
        endpoint = self._endpoint()
        params = self._parameters(endpoint)
        values: list[Any] = []
        for index, param in enumerate(params):
            component = str(param.get("component", "")).lower()
            label = str(param.get("label", "")).lower()
            if index == 0 or "text" in component or "prompt" in label or "message" in label:
                values.append(prompt)
            else:
                default = param.get("default")
                values.append(default if default is not None else None)
        result = self.client.predict(*values, api_name=endpoint)
        return self._extract_text(result)

    @staticmethod
    def _extract_text(result: Any) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, (list, tuple)):
            for item in reversed(result):
                text = QwenAgent._extract_text(item)
                if text:
                    return text
            return ""
        if isinstance(result, dict):
            for key in ("text", "output", "response", "content", "value"):
                if key in result:
                    text = QwenAgent._extract_text(result[key])
                    if text:
                        return text
            return json.dumps(result, ensure_ascii=False)
        return str(result) if result is not None else ""


def _get_agent() -> QwenAgent:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = QwenAgent()
    return _client


def _json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _fallback_plan(user_request: str) -> dict[str, Any]:
    lower = user_request.casefold()
    price = None
    price_match = re.search(r"(?:до|не дороже|макс(?:имум)?)\s*(\d[\d\s]{1,8})\s*(?:₽|руб|рублей)?", lower)
    if price_match:
        try:
            price = int(re.sub(r"\s+", "", price_match.group(1)))
        except ValueError:
            pass
    age = None
    age_match = re.search(r"(\d{1,2})\s*(?:лет|год(?:а)?)", lower)
    if age_match:
        age = int(age_match.group(1))
    gender = "мальчик" if "мальчик" in lower else "девочка" if "девочка" in lower else None
    return {
        "query": user_request.strip(),
        "category": None,
        "age": age,
        "gender": gender,
        "size": None,
        "max_price": price,
        "keywords": [],
        "marketplaces": ["wildberries", "ozon", "yandex_market", "simaland", "detmir", "akusherstvo", "korablik"],
        "limit": 20,
        "ai_parse_error": True,
    }


def agent_status() -> dict[str, Any]:
    try:
        agent = _get_agent()
        endpoint = agent._endpoint()
        return {"enabled": True, "space": SPACE, "endpoint": endpoint, "authenticated": bool(HF_TOKEN), "error": None}
    except Exception as exc:
        return {"enabled": False, "space": SPACE, "endpoint": None, "authenticated": bool(HF_TOKEN), "error": str(exc)}


def plan_search(user_request: str) -> dict[str, Any]:
    """Turn a natural-language shopping request into a safe search plan."""
    key = user_request.strip().casefold()
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < CACHE_TTL:
        return dict(cached[1])

    prompt = f'''Ты агент проекта «Мама, дешевле!». Разбери запрос покупателя и верни ТОЛЬКО JSON без markdown.
Поля: query (строка для поиска), category, age, gender, size, max_price, keywords (массив строк), marketplaces (массив только из wildberries, ozon, yandex_market, simaland, detmir, akusherstvo, korablik), limit (число 1-50).
Не выдумывай отсутствующие данные; неизвестные значения = null. marketplaces по умолчанию все семь источников.
Если пользователь просит конкретный магазин — выбери только его. Если просит маркетплейсы — выбери соответствующие маркетплейсы. Для общего поиска детских товаров используй все доступные источники.
Запрос: {user_request}'''

    try:
        text = _get_agent().generate(prompt)
        obj = _json_object(text) or _fallback_plan(user_request)
        obj["query"] = str(obj.get("query") or user_request).strip()
        obj["limit"] = max(1, min(int(obj.get("limit") or 20), 50))
        allowed = {"wildberries", "ozon", "yandex_market", "simaland", "detmir", "akusherstvo", "korablik"}
        markets = [str(x) for x in (obj.get("marketplaces") or []) if str(x) in allowed]
        obj["marketplaces"] = markets or sorted(allowed)
        if not isinstance(obj.get("keywords"), list):
            obj["keywords"] = []
        _cache[key] = (now, obj)
        return dict(obj)
    except Exception as exc:
        obj = _fallback_plan(user_request)
        obj["ai_error"] = str(exc)
        return obj
