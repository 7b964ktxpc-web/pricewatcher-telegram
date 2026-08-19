from __future__ import annotations

import os

from ai_agent import _get_agent
from ai_providers import deepseek, gemini, groq

TIMEOUT = float(os.getenv("AI_CHAT_TIMEOUT", "90"))

SYSTEM = """Ты дружелюбный AI-помощник проекта «Мама, дешевле!». Общайся естественно на русском. Помогай родителям искать детские товары и экономить. Не придумывай цены, наличие, скидки или ссылки: фактические данные сообщает поисковый агент. Если для поиска не хватает важных параметров, задай один короткий уточняющий вопрос. Если пользователь просто разговаривает — разговаривай, не запускай поиск. Отвечай кратко, тепло и по делу."""


def chat(messages: list[dict[str, str]]) -> str:
    prompt = SYSTEM + "\n\nИстория разговора:\n" + "\n".join(f"{m['role']}: {m['content']}" for m in messages[-10:]) + "\n\nОтветь на последнее сообщение пользователя."

    # Qwen/Hugging Face remains the primary conversational model.
    try:
        text = _get_agent().generate(prompt).strip()
        if text:
            return text
    except Exception as exc:
        print(f"Qwen chat unavailable: {exc}", flush=True)

    # Paid/optional providers are fallbacks only. A single provider outage must
    # never make the Telegram bot unusable.
    for provider in (deepseek, groq, gemini):
        try:
            result = provider.complete(prompt)
            if result.ok and result.text:
                return result.text
            if result.error not in {"disabled", "empty_response"}:
                print(f"{result.provider} chat unavailable: {result.error}", flush=True)
        except Exception as exc:
            print(f"{provider.__class__.__name__} chat unavailable: {exc}", flush=True)

    return "Я тебя поняла 🙂 Расскажи чуть подробнее, что тебе нужно — я помогу разобраться и при необходимости найду подходящие товары дешевле."


def status() -> dict[str, object]:
    return {
        "qwen": True,
        "deepseek_configured": deepseek.enabled,
        "groq_configured": groq.enabled,
        "gemini_configured": gemini.enabled,
        "providers": ["qwen_hf", "deepseek", "groq", "gemini"],
    }
