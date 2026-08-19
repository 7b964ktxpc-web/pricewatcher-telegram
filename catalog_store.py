from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_DB_PATH = Path(os.getenv("CATALOG_DB_PATH", "/opt/marketplace-parser/data/catalog.sqlite3"))
_LOCK = threading.RLock()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    with _LOCK, _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            product_key TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            marketplace TEXT,
            product_id TEXT,
            title TEXT NOT NULL,
            price REAL,
            old_price REAL,
            url TEXT,
            category TEXT,
            available INTEGER NOT NULL DEFAULT 1,
            payload_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_products_title ON products(title);
        CREATE INDEX IF NOT EXISTS idx_products_source ON products(source);
        CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);
        CREATE INDEX IF NOT EXISTS idx_products_available ON products(available);
        """)


def upsert_products(items: list[dict[str, Any]]) -> int:
    if not items:
        return 0
    now = time.time()
    rows = []
    for item in items:
        source = str(item.get("source") or "unknown")
        product_id = str(item.get("product_id") or item.get("id") or "")
        key = f"{source}:{product_id}" if product_id else f"{source}:{item.get('url','')}"
        rows.append((
            key, source, item.get("marketplace"), product_id,
            str(item.get("title") or ""), item.get("price"), item.get("old_price"),
            item.get("url"), item.get("category"), 1 if item.get("available", True) else 0,
            json.dumps(item, ensure_ascii=False), now,
        ))
    with _LOCK, _connect() as conn:
        conn.executemany("""
        INSERT INTO products(product_key,source,marketplace,product_id,title,price,old_price,url,category,available,payload_json,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(product_key) DO UPDATE SET
          marketplace=excluded.marketplace, title=excluded.title, price=excluded.price,
          old_price=excluded.old_price, url=excluded.url, category=excluded.category,
          available=excluded.available, payload_json=excluded.payload_json, updated_at=excluded.updated_at
        """, rows)
    return len(rows)


def search_catalog(query: str, limit: int = 50, max_price: float | None = None) -> list[dict[str, Any]]:
    terms = [x for x in query.lower().split() if len(x) >= 2][:8]
    if not terms:
        return []
    clauses = " AND ".join("lower(title) LIKE ?" for _ in terms)
    params: list[Any] = [f"%{term}%" for term in terms]
    sql = f"SELECT * FROM products WHERE available=1 AND {clauses}"
    if max_price is not None:
        sql += " AND price IS NOT NULL AND price <= ?"
        params.append(max_price)
    sql += " ORDER BY price ASC LIMIT ?"
    params.append(max(1, min(limit, 500)))
    with _LOCK, _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def stats() -> dict[str, Any]:
    init_db()
    with _LOCK, _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        available = conn.execute("SELECT COUNT(*) FROM products WHERE available=1").fetchone()[0]
        sources = conn.execute("SELECT source, COUNT(*) count FROM products GROUP BY source ORDER BY count DESC").fetchall()
    return {"db_path": str(_DB_PATH), "total": total, "available": available, "sources": [dict(x) for x in sources]}
