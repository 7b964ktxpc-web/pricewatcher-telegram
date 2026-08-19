from fastapi import FastAPI, HTTPException, Query
from normalizer import normalize_product
from providers import PROVIDERS, search_sources

app = FastAPI(title="Marketplace Parser Feed Engine", version="0.2.0")


@app.get("/")
def root():
    return {"service": "marketplace-parser", "version": app.version, "status": "ready"}


@app.get("/health")
def health():
    return {"ok": True, "service": "marketplace-parser", "version": app.version}


@app.get("/api/sources")
def sources():
    return {"sources": list(PROVIDERS), "mode": "independent-public-adapters"}


@app.get("/api/search")
def search(
    q: str = Query(min_length=1, max_length=300),
    limit: int = Query(default=20, ge=1, le=100),
    source: str | None = Query(default=None),
):
    selected = [source] if source else None
    if source and source not in PROVIDERS:
        raise HTTPException(400, f"Unknown source: {source}")
    return search_sources(q.strip(), limit, selected)


@app.get("/api/test-product")
def test_product():
    return normalize_product(
        source="test", marketplace="test", product_id="123",
        title="Тестовый товар", price=999, old_price=1999,
        url="https://example.com/product/123", category="Тест", available=True,
    )
