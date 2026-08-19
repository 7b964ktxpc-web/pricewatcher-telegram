from agent_router import resolve_sources
from ai_agent import _fallback_plan


def test_child_store_is_not_enabled_without_feed(monkeypatch):
    monkeypatch.delenv("DETMIR_FEED_URL", raising=False)
    assert "detmir_feed" not in resolve_sources(["detmir"])


def test_child_store_feed_is_resolved(monkeypatch):
    monkeypatch.setenv("DETMIR_FEED_URL", "https://example.test/detmir.xml")
    assert resolve_sources(["detmir"]) == ["detmir_feed"]


def test_marketplace_can_use_public_and_feed(monkeypatch):
    monkeypatch.setenv("OZON_FEED_URL", "https://example.test/ozon.xml")
    assert resolve_sources(["ozon"]) == ["ozon", "ozon_feed"]


def test_fallback_plan_knows_child_stores():
    plan = _fallback_plan("куртка мальчик 5 лет до 3000")
    assert "detmir" in plan["marketplaces"]
    assert plan["age"] == 5
    assert plan["max_price"] == 3000
