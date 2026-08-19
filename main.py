from fastapi import FastAPI
from normalizer import normalize_product

app = FastAPI(title="Marketplace Parser Feed Engine", version="0.1.0")

@app.get("/")
def root():
    return {"service": "marketplace-parser", "version": app.version, "status": "ready"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/test-product")
def test_product():
    return normalize_product(
        source="test", marketplace="test", product_id="123",
        title="Тестовый товар", price=999, old_price=1999,
        url="https://example.com/product/123", category="Тест", available=True,
    )
