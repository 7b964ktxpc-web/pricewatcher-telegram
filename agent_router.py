from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

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
            client = InferenceClient(api_key=os.environ["HF_TOKEN"])
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


def _local_fallback_plan(query: str) -> dict[str, Any]:
    lower = query.casefold()
    max_price = None
    price_match = re.search(r"(?:до|не дороже|макс(?:имум)?)\s*(\d[\d\s]{1,8})\s*(?:₽|руб(?:лей|ля)?)?", lower)
    if price_match:
        try:
            max_price = int(re.sub(r"\s+", "", price_match.group(1)))
        except ValueError:
            pass
    age = None
    age_match = re.search(r"(\d{1,2})\s*(?:лет|год(?:а)?)", lower)
    if age_match:
        age = int(age_match.group(1))
    gender = "мальчик" if "мальчик" in lower else "девочка" if "девочка" in lower else None
    category_map = {
        "футбол": "футболка", "футболк": "футболка", "джинс": "джинсы", "куртк": "куртка",
        "кроссов": "кроссовки", "плать": "платье", "обув": "обувь", "штаны": "штаны",
        "брюк": "брюки", "игруш": "игрушки", "рюкзак": "рюкзак",
    }
    category = next((value for needle, value in category_map.items() if needle in lower), None)
    return {
        "query": query.strip(), "category": category, "age": age, "gender": gender, "size": None,
        "max_price": max_price, "keywords": [category] if category else [],
        "marketplaces": sorted(ALLOWED_SOURCES), "limit": 20,
        "ai_parse_error": False, "plan_source": "local-fallback",
    }


def build_plan(query: str) -> dict[str, Any]:
    prompt = _prompt(query)
    providers = ["hf", "deepseek", "groq", "gemini"]
    plans: list[dict[str, Any]] = []
    env_keys = {"hf": "HF_TOKEN", "deepseek": "DEEPSEEK_API_KEY", "groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}
    configured = [p for p in providers if os.getenv(env_keys[p])]

    if configured:
        with ThreadPoolExecutor(max_workers=min(4, len(configured)), thread_name_prefix="ai-plan") as executor:
            futures = {executor.submit(_provider_plan, provider, prompt): provider for provider in configured}
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    result = future.result()
                except Exception:
                    result = None
                if result:
                    result["_provider"] = provider
                    plans.append(result)

    # Never block the production search on a public Gradio Space. If all
    # configured AI providers fail or none are configured, use deterministic
    # local parsing and continue to source discovery.
    if not plans:
        return _local_fallback_plan(query)

    def score(p: dict[str, Any]) -> int:
        return sum(p.get(k) is not None for k in ("category", "age", "gender", "size", "max_price")) + min(len(p.get("keywords") or []), 3)

    best = max(plans, key=score)
    markets = [x for x in best.get("marketplaces", []) if x in ALLOWED_SOURCES]
    best["marketplaces"] = markets or sorted(ALLOWED_SOURCES)
    best["agents_consulted"] = [p.get("_provider") for p in plans]
    best.pop("_provider", None)
    best.setdefault("ai_parse_error", False)
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
            "qwen_space": False,
            "huggingface_router": bool(os.getenv("HF_TOKEN")),
            "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
        },
        "sources": sorted(ALLOWED_SOURCES),
        "query_expansion": True,
        "bounded_agent_calls": 4,
        "feed_source_resolution": True,
    }
