from fastapi import FastAPI, HTTPException, Query
from normalizer import normalize_product
from provider_engine import search_sources
from providers import PROVIDERS

app = FastAPI(title="Marketplace Parser Feed Engine", version="0.6.0")

@app.get("/")
def root():
    return {"service": "marketplace-parser", "version": app.version, "status": "ready"}

@app.get("/health")
def health():
    return {"ok": True, "service": "marketplace-parser", "version": app.version}

@app.get("/api/sources")
def sources():
    return {"sources": list(PROVIDERS), "mode": "independent-public-adapters", "feed_env": {"wildberries_feed": "WB_FEED_URL", "ozon_feed": "OZON_FEED_URL", "yandex_market_feed": "YANDEX_MARKET_FEED_URL", "simaland_feed": "SIMALAND_FEED_URL"}}

@app.get("/api/ai/status")
def ai_status():
    from ai_agent import agent_status
    from agent_router import router_status
    return {"qwen": agent_status(), "router": router_status()}

@app.get("/api/ai/plan")
def ai_plan(q: str = Query(min_length=1, max_length=500)):
    from agent_router import build_plan
    try:
        return {"ok": True, "plan": build_plan(q)}
    except Exception as exc:
        raise HTTPException(503, f"AI unavailable: {exc}") from exc

@app.get("/api/agent/search")
def agent_search(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=20, ge=1, le=50)):
    """Multi-agent query planning + bounded source search + deterministic deal ranking."""
    from agent_router import build_plan, expand_queries
    from deal_ranker import rank_items

    plan = build_plan(q.strip())
    marketplaces = [str(x) for x in plan.get("marketplaces", []) if x in {"wildberries", "ozon", "yandex_market", "simaland"}]
    queries = expand_queries(plan, q.strip())
    runs = [search_sources(query, max(1, min(limit, 20)), marketplaces or None) for query in queries]

    collected: list[dict] = []
    for run in runs:
        collected.extend(run.get("items", []))

    max_price = plan.get("max_price")
    if isinstance(max_price, (int, float)):
        collected = [x for x in collected if isinstance(x.get("price"), (int, float)) and x["price"] <= max_price]

    items = rank_items(collected, plan, limit)
    return {
        "query": q.strip(),
        "count": len(items),
        "items": items,
        "queries": queries,
        "ai_plan": plan,
        "agent": "multi-agent-router",
        "runs": [{"query": r.get("query"), "count": r.get("count"), "sources": r.get("sources", [])} for r in runs],
        "ready": bool(items),
    }

@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=300), limit: int = Query(default=20, ge=1, le=100), source: str | None = Query(default=None)):
    selected = [source] if source else None
    allowed = {"wildberries", "ozon", "yandex_market", "simaland", *PROVIDERS}
    if source and source not in allowed:
        raise HTTPException(400, f"Unknown source: {source}")
    return search_sources(q.strip(), limit, selected)

@app.get("/api/test-product")
def test_product():
    return normalize_product(source="test", marketplace="test", product_id="123", title="Тестовый товар", price=999, old_price=1999, url="https://example.com/product/123", category="Тест", available=True)
