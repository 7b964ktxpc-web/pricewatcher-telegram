from __future__ import annotations

import json
import os
from typing import Any

from gradio_client import Client


SPACE = os.getenv("HF_AI_SPACE", "victor/Qwen3.8-27B-free-endpoint")
HF_TOKEN = os.getenv("HF_TOKEN") or None
TIMEOUT = float(os.getenv("HF_AI_TIMEOUT", "90"))


class QwenAgent:
    """Small, provider-agnostic agent adapter for a public Hugging Face Gradio Space.

    The Space endpoint is inspected at runtime, so the repository does not hard-code
    a fragile /predict signature. If the Space changes, the adapter can discover the
    new named endpoint through Gradio's API metadata.
    """

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
        # Most text endpoints expose one textbox prompt. For multi-input endpoints,
        # put the prompt into the first text-like parameter and use safe defaults.
        values: list[Any] = []
        for index, param in enumerate(params):
            component = str(param.get("component", "")).lower()
            if index == 0 or "text" in component or "prompt" in str(param.get("label", "")).lower():
                values.append(prompt)
            else:
                values.append(None)
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


def agent_status() -> dict[str, Any]:
    try:
        agent = QwenAgent()
        endpoint = agent._endpoint()
        return {"enabled": True, "space": SPACE, "endpoint": endpoint, "error": None}
    except Exception as exc:
        return {"enabled": False, "space": SPACE, "endpoint": None, "error": str(exc)}


def plan_search(user_request: str) -> dict[str, Any]:
    """Turn a natural-language shopping request into a safe search plan."""
    prompt = f'''Ты агент проекта «Мама, дешевле!». Разбери запрос покупателя и верни ТОЛЬКО JSON.
Поля: query (строка для поиска), category, age, gender, size, max_price, keywords (массив), marketplaces (массив из wildberries, ozon, yandex_market, simaland), limit (число 1-50).
Не выдумывай отсутствующие данные; неизвестные значения = null. marketplaces по умолчанию все четыре.
Запрос: {user_request}'''
    text = QwenAgent().generate(prompt)
    try:
        obj = json.loads(text[text.find("{"):text.rfind("}") + 1])
        obj["query"] = str(obj.get("query") or user_request).strip()
        obj["limit"] = max(1, min(int(obj.get("limit") or 20), 50))
        return obj
    except Exception:
        return {"query": user_request, "category": None, "age": None, "gender": None, "size": None, "max_price": None, "keywords": [], "marketplaces": ["wildberries", "ozon", "yandex_market", "simaland"], "limit": 20, "ai_parse_error": True}
