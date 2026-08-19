# Marketplace Parser

Independent marketplace/feed parser engine with an optional AI shopping agent and Telegram bot.

## Goals

- Collect product data from permitted APIs and partner/public feeds.
- Normalize prices, discounts, images, categories and availability.
- Let an AI understand natural-language shopping requests and turn them into structured search plans.
- Keep AI separate from catalog access: the AI plans/ranks; deterministic adapters fetch data.
- Expose a REST API for the web application and Telegram bot.
- Run the parser, Telegram bot and price watcher as separate Docker services.
- Persist the local catalog and user watchlists in Docker volumes.
- Deploy automatically from GitHub Actions.

## Architecture

`User -> Telegram -> Qwen/AI fallback -> Search Plan -> Marketplace/Feed/Web adapters -> Normalizer -> Matcher/Ranking -> Telegram`

The project does not depend on seller accounts for ordinary public/feed sources. Official partner credentials are used only by adapters that require them.

## Telegram bot

The bot is a separate service: `telegram-bot`.

It supports normal conversational Russian, not only commands:

- natural-language shopping requests;
- follow-up questions and context from the current conversation;
- `🔎 Найти дешевле`;
- `📸 По фото`;
- `💬 Просто поговорить`;
- `🔔 Мои товары`;
- `🛒 Купить`;
- `💰 Найти дешевле` for a found item;
- `🔄 Проверить` the current offer;
- `🔔 Следить` and remove an item from the watchlist;
- automatic price-drop notifications from the watcher service.

The Telegram token is never stored in source code. Docker Compose requires `TELEGRAM_BOT_TOKEN` from the deployment environment. The runner validates the token with Telegram `getMe` before entering the polling loop.

## AI

Qwen/Hugging Face is the primary conversational/search-planning provider. Optional fallback providers are DeepSeek, Groq and Gemini.

```text
HF_AI_SPACE=victor/Qwen3.8-27B-free-endpoint
HF_TOKEN=hf_...
HF_AI_TIMEOUT=90
HF_ROUTER_MODEL=Qwen/Qwen3-8B:fastest

DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-chat
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
```

AI is not trusted with factual prices: marketplace/feed adapters provide the product data and the ranking layer works on normalized offers.

## Sources

Supported source families include:

- Wildberries public/feed path;
- Ozon public/feed path;
- Яндекс Маркет public/feed path and official partner adapter;
- Сима-Ленд feed path;
- additional child-focused feeds such as Детский мир, Акушерство and Кораблик when a permitted structured feed is configured.

Source health uses a circuit breaker so repeatedly blocked public endpoints enter cooldown instead of being hammered.

## REST API

- `GET /` — service identity
- `GET /health` — liveness
- `GET /api/readiness` — deployment readiness without exposing credentials
- `GET /api/connections` — configured integration status
- `GET /api/sources` — source registry
- `GET /api/marketplace-adapters` — marketplace adapter status
- `GET /api/feed-adapters` — configured feed status
- `GET /api/feed-import` — import configured feeds into the local catalog
- `GET /api/catalog?q=...` — local catalog search
- `GET /api/catalog/stats` — catalog counters
- `GET /api/source-health` — source circuit-breaker state
- `GET /api/ai/status` — AI provider status
- `GET /api/ai/plan?q=...` — natural-language search plan
- `GET /api/web-research?q=...` — web research pipeline
- `GET /api/child-search?q=...` — child-goods search compatibility route
- `GET /api/agent/search?q=...` — full multi-source AI search
- `GET /api/search?q=...` — deterministic source search

Example:

```text
/api/agent/search?q=футболка%20мальчик%205%20лет%20до%201000%20рублей
```

## Docker

```bash
docker compose up --build -d
```

Services:

- `marketplace-parser` — REST API and catalog engine;
- `telegram-bot` — Telegram polling, natural conversation, buttons and photo search;
- `watchlist-checker` — periodic price checks and Telegram alerts.

The parser exposes port `8010`. The bot and watcher communicate with it over the Docker network.

Persistent volumes:

- `parser-data` — catalog database;
- `telegram-data` — user watchlists.

## CI

GitHub Actions runs, in order:

1. Python compilation;
2. runtime smoke test;
3. complete pytest suite;
4. Docker image build.

A green CI run is the required gate before production deployment.

## Production completion checklist

1. CI green.
2. Docker image builds successfully.
3. `/health` returns `ok: true`.
4. `/api/readiness` reports Telegram and at least one AI provider configured.
5. At least one permitted marketplace/feed source is configured for real product data.
6. Telegram `getMe` succeeds at bot startup.
7. `/start`, natural conversation, buttons and photo search are verified in Telegram.
8. A real product search returns normalized offers with price and URL where available.
9. `🔔 Следить` persists the item and `watchlist-checker` can re-check it.
10. A real price decrease produces one Telegram notification.

The final production step is deployment on the Russian VPS with the secrets supplied through the server/CI environment; credentials must not be committed to the repository.
