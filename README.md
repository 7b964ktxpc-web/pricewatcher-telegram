# Marketplace Parser

Independent marketplace/feed parser engine with an optional AI shopping agent.

## Goals

- Collect product data from permitted APIs and partner/public feeds.
- Normalize prices, discounts, images, categories and availability.
- Let an AI understand natural-language shopping requests and turn them into structured search plans.
- Keep AI separate from catalog access: the AI plans/ranks; deterministic adapters fetch data.
- Expose a REST API for the web application and Telegram bot.
- Run in Docker on a Russian VPS.
- Deploy automatically from GitHub Actions.

## Architecture

`User -> Qwen Agent -> Search Plan -> Source Adapters -> Normalizer -> Ranking -> API`

The project does not depend on seller accounts for marketplaces.

## AI agent

The first provider is the public Hugging Face Space `victor/Qwen3.8-27B-free-endpoint`. Hugging Face documents that Gradio Spaces are callable as APIs and expose runtime API metadata; the adapter therefore discovers the available named text endpoint instead of hard-coding a fragile endpoint signature.

Optional environment variables:

```text
HF_AI_SPACE=victor/Qwen3.8-27B-free-endpoint
HF_TOKEN=hf_...
HF_AI_TIMEOUT=90
```

`HF_TOKEN` is optional for a public Space, but authentication can provide better rate limits. Free/ZeroGPU usage is quota-limited, so the catalog engine remains functional without AI and AI is not used to fetch marketplace pages directly.

## API

- `GET /health` — service health
- `GET /api/sources` — configured sources
- `GET /api/search?q=...` — deterministic source search
- `GET /api/ai/status` — AI provider status and discovered endpoint
- `GET /api/ai/plan?q=...` — convert a natural-language request to a search plan
- `GET /api/agent/search?q=...` — AI plan + catalog search + price filtering

Example:

```text
/api/agent/search?q=футболка%20мальчик%205%20лет%20до%201000%20рублей
```

## Development

```bash
docker compose up --build
```

Health endpoint: `GET /health`
