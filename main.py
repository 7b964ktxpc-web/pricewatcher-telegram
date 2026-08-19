from concurrent.futures import ThreadPoolExecutor, as_completed
import os

from fastapi import FastAPI, HTTPException, Query
from normalizer import normalize_product
from resilient_provider_engine import search_sources
from providers import PROVIDERS
from source_registry import source_status
from source_discovery import discover_sources
from catalog_store import init_db, search_catalog, stats as catalog_stats, upsert_products

app = FastAPI(title="Marketplace Parser Feed Engine", version="0.20.0")
init_db()


def summarize_feed_readiness(feeds):
    """Normalize the feed-manager public contract for readiness responses."""
    if isinstance(feeds, dict):
        configured = feeds.get("configured", [])
        results = feeds.get("results", [])
        return {
            "configured": len(configured) if isinstance(configured, (list, tuple, set)) else 0,
            "total": int(feeds.get("checked", len(results) if isinstance(results, list) else 0)),
            "items": feeds,
        }
    if isinstance(feeds, (list, tuple)):
        items = [item for item in feeds if isinstance(item, dict)]
        return {
            "configured": sum(1 for item in items if item.get("configured")),
            "total": len(feeds),
            "items": feeds,
        }
    return {"configured": 0, "total": 0, "items": feeds}

@app.get("/")
def root():
    return {"service": "marketplace-parser", "version": app.version, "status": "ready"}

@app.get("/health")
def health():
    return {"ok": True, "service": "marketplace-parser", "version": app.version}

@app.get("/api/sources")
def sources():
    return {"sources": list(PROVIDERS), "registry": source_status(), "mode": "web-research-plus-public-feeds-plus-official-apis"}

@app.get("/api/marketplace-adapters")
def marketplace_adapters():
    from marketplace_adapters import adapter_status
    return {"adapters": adapter_status()}

@app.get("/api/connections")
def connections():
    """Safe connection dashboard: exposes configuration state, never credentials."""
    from marketplace_adapters import adapter_status
    from feed_adapter_manager import inspect_feeds
    from conversation_agent import status as chat_status
    adapters = adapter_status()
    feeds = inspect_feeds()
    return {
        "marketplace_apis": adapters,
        "partner_feeds": feeds,
        "ai": {
            "hf_token_configured": bool(os.getenv("HF_TOKEN")),
            "groq_configured": bool(os.getenv("GROQ_API_KEY")),
            "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
            "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
            "chat": chat_status(),
        },
        "telegram": {"token_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN"))},
    }

@app.get("/api/readiness")
def readiness():
    """Deployment-safe readiness report for the main integrations."""
    from marketplace_adapters import adapter_status
    from feed_adapter_manager import inspect_feeds
    from conversation_agent import status as chat_status

    adapters = adapter_status()
    feeds = inspect_feeds()
    ai = chat_status()
    configured_marketplaces = sum(1 for item in adapters if isinstance(item, dict) and item.get("configured"))
    feed_summary = summarize_feed_readiness(feeds)

    ai_ready = bool(ai.get("qwen") or ai.get("deepseek_configured") or ai.get("groq_configured") or ai.get("gemini_configured"))
    telegram_ready = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
    return {
        "ready": bool(telegram_ready and ai_ready),
        "telegram": {"configured": telegram_ready},
        "ai": {"ready": ai_ready, "providers": ai.get("providers", [])},
        "marketplaces": {"configured": configured_marketplaces, "total": len(adapters), "items": adapters},
        "feeds": feed_summary,
        "next": "connect at least one marketplace/feed for real product data" if configured_marketplaces + feed_summary["configured"] == 0 else "run a real Telegram search",
    }

@app.get("/api/discovery")
def discovery():
    return discover_sources()

@app.get("/api/feed-adapters")
def feed_adapters():
    from feed_adapter_manager import inspect_feeds
    return inspect_feeds()

@app.get("/api/feed-import")
def feed_import(limit: int = Query(default=5000, ge=1, le=50000)):
    from feed_import_engine import import_all
    result = import_all(limit=limit)
    stored = upsert_products(result.get("items", []))
    result["stored"] = stored
    result["catalog"] = catalog_stats()
    return result

@app.get("/api/catalog")
def catalog(q: str = Query(min_length=1, max_length=300), limit: int = Query(default=50, ge=1, le=500), max_price: float | None = Query(default=None, ge=0)):
    items = search_catalog(q.strip(), limit, max_price)
    return {"query": q.strip(), "count": len(items), "items": items, "source": "local-catalog"}

@app.get("/api/catalog/stats")
def catalog_statistics():
    return catalog_stats()

@app.get("/api/source-health")
def source_health():
    from source_health import source_health_snapshot
    return {"sources": source_health_snapshot()}

@app.get("/api/ai/status")
def ai_status():
    from ai_agent import agent_status
    from agent_router import router_status
    from conversation_agent import status as chat_status
    return {"qwen": agent_status(), "router": router_status(), "chat": chat_status()}

@app.get("/api/ai/plan")
def ai_plan(q: str = Query(min_length=1, max_length=500)):
    from agent_router import build_plan
    try:
        return {"ok": True, "plan": build_plan(q)}
    except Exception as exc:
        raise HTTPException(503, f"AI unavailable: {exc}") from exc

@app.get("/api/web-research")
def web_research(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=8, ge=1, le=20), fetch_pages: bool = Query(default=True)):
    from agent_web_pipeline import search_web
    result = search_web(q.strip(), limit)
    result["fetch_pages_requested"] = fetch_pages
    result["fetch_pages_effective"] = True
    return result

@app.get("/api/child-search")
def child_search(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=12, ge=1, le=30)):
    from child_deal_search import search_child_deals
    try:
        return search_child_deals(q.strip(), limit)
    except Exception as exc:
        raise HTTPException(502, f"Child deal search failed: {exc}") from exc

@app.get("/api/agent/search")
def agent_search(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=20, ge=1, le=50)):
    from agent_router import build_plan, expand_queries, resolve_sources
    from deal_ranker import rank_items
    from product_matcher import group_products
    from agent_web_pipeline import search_web_batch

    query_text = q.strip()
    plan = build_plan(query_text)
    requested = [str(x) for x in plan.get("marketplaces", [])]
    sources = resolve_sources(requested)
    queries = expand_queries(plan, query_text)

    max_workers = max(1, min(len(queries), int(os.getenv("QUERY_SEARCH_WORKERS", str(len(queries))))))
    runs_by_query: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="query") as executor:
        futures = {executor.submit(search_sources, query, max(1, min(limit, 20)), sources or None): query for query in queries}
        for future in as_completed(futures):
            query = futures[future]
            try:
                runs_by_query[query] = future.result()
            except Exception as exc:
                runs_by_query[query] = {"query": query, "count": 0, "items": [], "sources": [], "ready": False, "error": str(exc)}

    runs = [runs_by_query.get(query, {"query": query, "count": 0, "items": [], "sources": []}) for query in queries]
    collected: list[dict] = []
    for run in runs:
        collected.extend(run.get("items", []))

    web_runs = search_web_batch(queries, limit=min(6, limit))
    web_items = [item for run in web_runs for item in run.get("items", [])]
    collected.extend(web_items)

    max_price = plan.get("max_price")
    if isinstance(max_price, (int, float)):
        collected = [x for x in collected if x.get("discovery_only") or (isinstance(x.get("price"), (int, float)) and x["price"] <= max_price)]

    collected.extend(search_catalog(query_text, max(20, limit * 3), max_price if isinstance(max_price, (int, float)) else None))
    ranked = rank_items(collected, plan, max(1, limit * 3))
    groups = group_products(ranked, threshold=float(os.getenv("PRODUCT_MATCH_THRESHOLD", "0.72")))
    items = [group["best_offer"] | {"offer_count": group["offer_count"], "lowest_price": group["lowest_price"], "match_group": group["match_group"]} for group in groups[:limit]]

    return {"query": query_text, "count": len(items), "items": items, "product_groups": groups[:limit], "queries": queries, "ai_plan": plan, "requested_sources": requested, "resolved_sources": sources, "web_research": {"runs": len(web_runs), "items": len(web_items), "sources": sorted({str(i.get("source")) for i in web_items if i.get("source")}, key=str)}, "agent": "multi-agent-router", "parallel": {"queries": len(queries), "sources_per_query": len(sources), "web_research_runs": len(web_runs)}, "runs": [{"query": r.get("query"), "count": r.get("count"), "sources": r.get("sources", []), "error": r.get("error")} for r in runs], "ready": bool(items)}

@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=300), limit: int = Query(default=20, ge=1, le=100), source: str | None = Query(default=None)):
    selected = [source] if source else None
    allowed = set(PROVIDERS)
    if source and source not in allowed:
        raise HTTPException(400, f"Unknown source: {source}")
    return search_sources(q.strip(), limit, selected)

@app.get("/api/test-product")
def test_product():
    return normalize_product(source="test", marketplace="test", product_id="123", title="Тестовый товар", price=999, old_price=1999, url="https://example.com/product/123", category="Тест", available=True)
