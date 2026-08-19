from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from ai_agent import plan_search

ALLOWED_MARKETPLACES = {"wildberries", "ozon", "yandex_market", "simaland"}
TIMEOUT = float(os.getenv("AI_ROUTER_TIMEOUT", "20"))


def _extract_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    candidates = [m.group(1)] if m else []
    candidates.append(text)
    a, b = text.find("{"), text.rfind("}")
    if a >= 0 and b > a:
        candidates.append(text[a:b + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    return None


def _openai_chat(base_url: str, api_key: str, model: str, prompt: str) -> dict[str, Any]:
    r = requests.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 500},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    text = data["choices"][0]["message"]["content"]
    return _extract_json(text) or {}


def _provider_plan(name: str, prompt: str) -> dict[str, Any] | None:
    try:
        if name == "groq" and os.getenv("GROQ_API_KEY"):
            return _openai_chat("https://api.groq.com/openai/v1", os.environ["GROQ_API_KEY"], os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"), prompt)
        if name == "gemini" and os.getenv("GEMINI_API_KEY"):
            # Gemini is optional; use its OpenAI-compatible endpoint when enabled.
            return _openai_chat("https://generativelanguage.googleapis.com/v1beta/openai", os.environ["GEMINI_API_KEY"], os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), prompt)
        if name == "hf" and os.getenv("HF_TOKEN"):
            from huggingface_hub import InferenceClient
            client = InferenceClient(token=os.environ["HF_TOKEN"])
            model = os.getenv("HF_ROUTER_MODEL", "Qwen/Qwen3-8B")
            response = client.chat_completion(model=model, messages=[{"role": "user", "content": prompt}], max_tokens=500, temperature=0)
            return _extract_json(response.choices[0].message.content) or {}
    except Exception:
        return None
    return None


def _prompt(query: str) -> str:
    return f'''Разбери покупательский запрос. Верни JSON: query, category, age, gender, size, max_price, keywords, marketplaces. marketplaces выбирай только из wildberries, ozon, yandex_market, simaland. Если данных нет — null. Не выдумывай. Запрос: {query}'''


def build_plan(query: str) -> dict[str, Any]:
    prompt = _prompt(query)
    providers = ["groq", "gemini", "hf"]
    plans: list[dict[str, Any]] = []
    for provider in providers:
        result = _provider_plan(provider, prompt)
        if result:
            result["_provider"] = provider
            plans.append(result)

    # Qwen Space remains the default specialist and final fallback.
    qwen = plan_search(query)
    if qwen and not qwen.get("ai_parse_error"):
        qwen["_provider"] = "qwen-space"
        plans.append(qwen)

    if not plans:
        return qwen

    # Prefer a plan that specifies more concrete constraints; this reduces
    # hallucinated broad searches when several free agents disagree.
    def score(p: dict[str, Any]) -> int:
        return sum(p.get(k) is not None for k in ("category", "age", "gender", "size", "max_price")) + min(len(p.get("keywords") or []), 3)

    best = max(plans, key=score)
    markets = [x for x in best.get("marketplaces", []) if x in ALLOWED_MARKETPLACES]
    best["marketplaces"] = markets or sorted(ALLOWED_MARKETPLACES)
    best["agents_consulted"] = [p.get("_provider") for p in plans]
    best.pop("_provider", None)
    return best


def expand_queries(plan: dict[str, Any], original: str) -> list[str]:
    base = str(plan.get("query") or original).strip()
    queries = [base]
    category = plan.get("category")
    gender = plan.get("gender")
    age = plan.get("age")
    size = plan.get("size")
    keywords = [str(x).strip() for x in plan.get("keywords", []) if str(x).strip()]
    if category:
        parts = [str(category)]
        if gender: parts.append(str(gender))
        if age is not None: parts.append(f"{age} лет")
        if size: parts.append(str(size))
        queries.append(" ".join(parts))
    if keywords:
        queries.append(" ".join([str(category or "детские товары"), *keywords]))
    # Stable, bounded expansion: no uncontrolled agent loops.
    return list(dict.fromkeys(q for q in queries if q))[:3]


def router_status() -> dict[str, Any]:
    return {
        "agents": {
            "qwen_space": True,
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "huggingface_router": bool(os.getenv("HF_TOKEN")),
        },
        "marketplaces": sorted(ALLOWED_MARKETPLACES),
        "query_expansion": True,
        "bounded_agent_calls": 4,
    }
