def test_search_pipeline_imports():
    from child_deal_search import search_child_deals
    from price_verifier import verify_url
    from product_offer_matcher import group_offers
    from verified_deal_pipeline import build_verified_deals
    from web_product_extractor import extract_product_page
    from web_research_engine import fetch_page, research

    assert callable(search_child_deals)
    assert callable(verify_url)
    assert callable(group_offers)
    assert callable(build_verified_deals)
    assert callable(extract_product_page)
    assert callable(fetch_page)
    assert callable(research)
