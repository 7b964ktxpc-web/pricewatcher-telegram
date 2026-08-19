from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from ai_agent import plan_search
from feed_adapters import FEED_ADAPTERS

ALLOWED_SOURCES = {"wildberries", "ozon", "yandex_market", "simaland", "detmir", "akusherstvo", "korablik"}
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
        if name == "hf" and os.getenv("HF_TOKEN"):
            from huggingface_hub import InferenceClient
            client = InferenceClient(token=os.environ["HF_TOKEN"])
            model = os.getenv("HF_ROUTER_MODEL", "Qwen/Qwen3-8B:fastest")
            response = client.chat_completion(model=model, messages=[{"role": "user", "content": prompt}], max_tokens=500, temperature=0)
            return _extract_json(response.choices[0].message.content) or {}
        if name == "deepseek" and os.getenv("DEEPSEEK_API_KEY"):
            return _openai_chat("https://api.deepseek.com", os.environ["DEEPSEEK_API_KEY"], os.getenv("DEEPSEEK_MODEL", "deepseek-chat"), prompt)
        if name == "groq" and os.getenv("GROQ_API_KEY"):
            return _openai_chat("https://api.groq.com/openai/v1", os.environ["GROQ_API_KEY"], os.environ["GROQ_MODEL"], prompt)
        if name == "gemini" and os.getenv("GEMINI_API_KEY"):
            return _openai_chat("https://generativelanguage.googleapis.com/v1beta/openai", os.environ["GEMINI_API_KEY"], os.environ["GEMINI_MODEL"], prompt)
    except Exception:
        return None
    return None


def _prompt(query: str) -> str:
    return f'''Разбери покупательский запрос. Верни JSON: query, category, age, gender, size, max_price, keywords, marketplaces. marketplaces выбирай только из wildberries, ozon, yandex_market, simaland, detmir, akusherstvo, korablik. Если данных нет — null. Не выдумывай. Запрос: {query}'''


def build_plan(query: str) -> dict[str, Any]:
    prompt = _prompt(query)
    # Prefer HF routed inference because one HF token can route to multiple
    # providers/models. Direct providers remain fallbacks when their secrets exist.
    providers = ["hf", "deepseek", "groq", "gemini"]
    plans: list[dict[str, Any]] = []
    for provider in providers:
        result = _provider_plan(provider, prompt)
        if result:
            result["_provider"] = provider
            plans.append(result)

    qwen = plan_search(query)
    if qwen and not qwen.get("ai_parse_error"):
        qwen["_provider"] = "qwen-space"
        plans.append(qwen)

    if not plans:
        return qwen

    def score(p: dict[str, Any]) -> int:
        return sum(p.get(k) is not None for k in ("category", "age", "gender", "size", "max_price")) + min(len(p.get("keywords") or []), 3)

    best = max(plans, key=score)
    markets = [x for x in best.get("marketplaces", []) if x in ALLOWED_SOURCES]
    best["marketplaces"] = markets or sorted(ALLOWED_SOURCES)
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
    return list(dict.fromkeys(q for q in queries if q))[:3]


def resolve_sources(names: list[str]) -> list[str]:
    resolved: list[str] = []
    for name in names:
        if name in FEED_ADAPTERS:
            adapter = FEED_ADAPTERS[name]
            if adapter.configured():
                resolved.append(name)
            continue
        if name in {"wildberries", "ozon", "yandex_market", "simaland"}:
            resolved.append(name)
            feed_key = f"{name}_feed"
            adapter = FEED_ADAPTERS.get(feed_key)
            if adapter and adapter.configured():
                resolved.append(feed_key)
        elif name in {"detmir", "akusherstvo", "korablik"}:
            feed_key = f"{name}_feed"
            adapter = FEED_ADAPTERS.get(feed_key)
            if adapter and adapter.configured():
                resolved.append(feed_key)
    return list(dict.fromkeys(resolved))


def router_status() -> dict[str, Any]:
    return {
        "agents": {
            "qwen_space": True,
            "huggingface_router": bool(os.getenv("HF_TOKEN")),
            "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
        },
        "sources": sorted(ALLOWED_SOURCES),
        "query_expansion": True,
        "bounded_agent_calls": 5,
        "feed_source_resolution": True,
    }
