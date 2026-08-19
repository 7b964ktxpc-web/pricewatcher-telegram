# Marketplace Parser

Independent marketplace/feed parser engine.

## Goals

- Collect product data from permitted APIs and partner feeds.
- Normalize prices, discounts, images, categories and availability.
- Expose a REST API for the web application.
- Run in Docker on a Russian VPS.
- Deploy automatically from GitHub Actions.

## Architecture

`Sources -> Adapters -> Normalizer -> Storage -> Search API -> Web`

The project does not depend on seller accounts for marketplaces.

## Development

```bash
docker compose up --build
```

Health endpoint: `GET /health`
