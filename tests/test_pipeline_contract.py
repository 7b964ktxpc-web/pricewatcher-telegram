import importlib


MODULES = [
    "source_search",
    "web_research_engine",
    "web_product_extractor",
    "price_verifier",
    "verified_deal_pipeline",
    "product_identity",
    "product_offer_matcher",
    "agent_web_pipeline",
    "child_deal_search",
]


def test_pipeline_modules_import():
    for name in MODULES:
        module = importlib.import_module(name)
        assert module is not None


def test_pipeline_entrypoints_exist():
    from agent_web_pipeline import search_web
    from child_deal_search import search_child_deals
    from price_verifier import verify_url
    from product_offer_matcher import group_offers
    from verified_deal_pipeline import build_verified_deals

    assert callable(search_web)
    assert callable(search_child_deals)
    assert callable(verify_url)
    assert callable(group_offers)
    assert callable(build_verified_deals)
