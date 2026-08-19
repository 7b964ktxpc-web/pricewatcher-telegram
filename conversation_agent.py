from __future__ import annotations

import os
import requests
from ai_agent import _get_agent

TIMEOUT = float(os.getenv("AI_CHAT_TIMEOUT", "90"))
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM = """Ты дружелюбный AI-помощник проекта «Мама, дешевле!». Общайся естественно на русском. Помогай родителям искать детские товары и экономить. Не придумывай цены, наличие, скидки или ссылки: фактические данные сообщает поисковый агент. Если для поиска не хватает важных параметров, задай один короткий уточняющий вопрос. Если пользователь просто разговаривает — разговаривай, не запускай поиск. Отвечай кратко, тепло и по делу."""


def _deepseek(messages: list[dict[str, str]]) -> str | None:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        return None
    try:
        response = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": DEEPSEEK_MODEL, "messages": [{"role": "system", "content": SYSTEM}, *messages], "temperature": 0.7, "max_tokens": 300},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"]).strip()
    except Exception as exc:
        print(f"DeepSeek chat unavailable: {exc}", flush=True)
        return None


def chat(messages: list[dict[str, str]]) -> str:
    try:
        prompt = SYSTEM + "\n\nИстория разговора:\n" + "\n".join(f"{m['role']}: {m['content']}" for m in messages[-10:]) + "\n\nОтветь на последнее сообщение пользователя."
        text = _get_agent().generate(prompt).strip()
        if text:
            return text
    except Exception as exc:
        print(f"Qwen chat unavailable: {exc}", flush=True)
    fallback = _deepseek(messages)
    if fallback:
        return fallback
    return "Я тебя поняла 🙂 Расскажи чуть подробнее, что тебе нужно — я помогу разобраться и при необходимости найду подходящие товары дешевле."


def status() -> dict[str, object]:
    return {"qwen": True, "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY")), "deepseek_model": DEEPSEEK_MODEL}
