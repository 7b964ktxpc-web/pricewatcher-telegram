from __future__ import annotations

from fastapi import APIRouter, Query

from web_research_engine import research

router = APIRouter(prefix="/api/web-research", tags=["web-research"])


@router.get("")
def web_research(
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=8, ge=1, le=20),
    fetch_pages: bool = Query(default=True),
):
    """Search the public web for product/deal discovery.

    This endpoint is intentionally independent from marketplace APIs. The
    returned pages are discovery evidence and must be verified before being
    presented as a live price/availability claim.
    """
    return research(q.strip(), limit=limit, fetch_pages=fetch_pages)
