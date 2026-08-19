from source_search import source_queries


def test_source_queries_cover_target_sources():
    result = source_queries(["детские кроссовки 33"])
    names = {item["source"] for item in result}
    assert {"pepper", "ozon", "wildberries", "yandex_market", "sima_land", "detmir"}.issubset(names)
    assert all(item["query"].startswith("site:") for item in result)
