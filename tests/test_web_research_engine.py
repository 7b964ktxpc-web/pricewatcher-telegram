from web_research_engine import _domain, _source_for, _unwrap_url


def test_domain_and_source_detection():
    assert _domain("https://www.ozon.ru/product/x") == "ozon.ru"
    assert _source_for("https://www.wildberries.ru/catalog/123/detail.aspx") == "wildberries"
    assert _source_for("https://www.pepper.ru/deals/example") == "pepper"


def test_duckduckgo_redirect_is_unwrapped():
    target = "https://www.ozon.ru/product/example"
    url = "https://duckduckgo.com/l/?uddg=" + target.replace(":", "%3A").replace("/", "%2F")
    assert _unwrap_url(url) == target


def test_unknown_source_falls_back_to_domain():
    assert _source_for("https://example.org/product") == "example.org"
