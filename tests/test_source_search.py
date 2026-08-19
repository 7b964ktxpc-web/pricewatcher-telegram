from source_search import source_queries


def test_source_queries_cover_target_sources():
    result = source_queries(["детские кроссовки 33"])
    names = {item["source"] for item in result}
    assert {"pepper", "ozon", "wildberries", "yandex_market", "sima_land", "detmir", "kapika"}.issubset(names)
    assert all(item["query"].startswith("site:") for item in result)


def test_kapika_queries_use_real_child_store_domain():
    result = source_queries(["детские кроссовки 33"])
    kapika = [item for item in result if item["source"] == "kapika"]
    assert kapika
    assert kapika[0]["domain"] == "kapika.ru"
    assert "site:kapika.ru" in kapika[0]["query"]
