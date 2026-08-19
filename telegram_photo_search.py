from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

import requests

VISION_API_URL = os.getenv("VISION_API_URL", "https://router.huggingface.co/hf-inference/models/Qwen/Qwen2.5-VL-7B-Instruct").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
TIMEOUT = float(os.getenv("VISION_TIMEOUT", "45"))


def _prompt() -> str:
    return (
        "Ты визуальный помощник магазина детских товаров. Опиши товар на фото для поиска в интернете. "
        "Верни только JSON: {\"query\": string, \"category\": string|null, "
        "\"gender\": string|null, \"age\": number|null, \"color\": string|null, "
        "\"brand\": string|null, \"size\": string|null, \"keywords\": [string]}. "
        "Не выдумывай характеристики, которых не видно. Если товар не детский, всё равно опиши его буквально."
    )


def _extract(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            value = json.loads(match.group(0))
            if isinstance(value, dict) and value.get("query"):
                return value
        except json.JSONDecodeError:
            pass
    return {"query": text.strip(), "category": None, "gender": None, "age": None, "color": None, "brand": None, "size": None, "keywords": []}


def describe_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN is required for photo search")
    encoded = base64.b64encode(image_bytes).decode("ascii")
    response = requests.post(
        VISION_API_URL,
        headers={"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"},
        json={"inputs": {"image": encoded, "text": _prompt()}},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        text = str(data.get("generated_text") or data.get("text") or data.get("answer") or data)
    elif isinstance(data, list):
        first = data[0] if data else {}
        text = str(first.get("generated_text") or first.get("text") or first) if isinstance(first, dict) else str(first)
    else:
        text = str(data)
    return _extract(text)
