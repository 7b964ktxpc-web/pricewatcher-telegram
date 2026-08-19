from child_query_parser import build_search_queries, parse_child_query


def test_parse_child_query():
    parsed = parse_child_query('зимняя куртка мальчику 5 лет размер 116 до 5000 ₽')
    assert parsed['age_years'] == 5
    assert parsed['gender'] == 'boy'
    assert parsed['size'] == 116
    assert parsed['budget_max'] == 5000
    assert parsed['category'] == 'outerwear'


def test_build_queries():
    parsed = parse_child_query('кроссовки девочке 8 лет размер 33 до 2500')
    queries = build_search_queries(parsed)
    assert any('для девочки' in q for q in queries)
    assert any('2500' in q for q in queries)
