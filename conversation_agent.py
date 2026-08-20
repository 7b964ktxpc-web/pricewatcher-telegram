from __future__ import annotations

import os

from ai_agent import _get_agent
from ai_providers import deepseek, gemini, groq

TIMEOUT = float(os.getenv("AI_CHAT_TIMEOUT", "90"))

SYSTEM = """Ты дружелюбный помощник проекта «Мама, дешевле!». Общайся с человеком естественно, как хороший внимательный помощник, а не как справочная система.

Правила общения:
- Отвечай на русском, тепло, коротко и живо.
- Не начинай каждый ответ одинаково и не используй шаблонные фразы вроде «Конечно! Я с радостью помогу» без причины.
- Учитывай историю разговора и не заставляй человека повторять уже сказанное.
- Если человек уточняет запрос («а подешевле?», «а есть синий?», «для девочки», «покажи другие»), воспринимай это как продолжение разговора.
- Если для поиска действительно не хватает важного параметра, задай только один короткий уточняющий вопрос.
- Не задавай вопросы ради вопросов: если можно сделать разумное предположение, сделай его.
- Не придумывай цены, наличие, скидки, магазины или ссылки. Фактические данные сообщает live search agent.
- Если человек просто разговаривает, поддержи разговор и не запускай поиск автоматически.
- Если человек недоволен результатом, спокойно предложи изменить критерий или поискать альтернативы.
- Не говори о себе как о программе, модели, API или внутренней архитектуре.
- Не рассказывай пользователю про провайдеров ИИ, промпты, fallback или технические ошибки.
- Не используй канцелярит и длинные списки, если человек задал простой вопрос.

Твоя задача — помочь человеку быстро найти подходящий товар и почувствовать, что с ним действительно разговаривают, а не обрабатывают форму запроса."""


def chat(messages: list[dict[str, str]]) -> str:
    history = messages[-10:]
    prompt = SYSTEM + "\n\nИстория разговора:\n" + "\n".join(
        f"{m['role']}: {m['content']}" for m in history
    ) + "\n\nОтветь на последнее сообщение пользователя, продолжая разговор естественно."

    try:
        text = _get_agent().generate(prompt).strip()
        if text:
            return text
    except Exception as exc:
        print(f"Qwen chat unavailable: {exc}", flush=True)

    for provider in (deepseek, groq, gemini):
        try:
            result = provider.complete(prompt)
            if result.ok and result.text:
                return result.text
            if result.error not in {"disabled", "empty_response"}:
                print(f"{result.provider} chat unavailable: {result.error}", flush=True)
        except Exception as exc:
            print(f"{provider.__class__.__name__} chat unavailable: {exc}", flush=True)

    return "Поняла 🙂 Давай разберёмся. Что именно хочешь изменить или найти?"


def status() -> dict[str, object]:
    return {
        "qwen": True,
        "deepseek_configured": deepseek.enabled,
        "groq_configured": groq.enabled,
        "gemini_configured": gemini.enabled,
        "providers": ["qwen_hf", "deepseek", "groq", "gemini"],
    }
