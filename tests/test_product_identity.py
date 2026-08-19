from product_identity import identity, match_score


def test_same_article_is_strong_match():
    a = identity("Nike Air Max детские 33", {"article": "ABC-123", "brand": "Nike"})
    b = identity("Nike Air Max 33", {"article": "ABC-123", "brand": "Nike"})
    assert match_score(a, b) == 0.98


def test_different_articles_are_not_exact_matches():
    a = identity("Nike Air Max 33", {"article": "A"})
    b = identity("Nike Air Max 33", {"article": "B"})
    assert match_score(a, b) < 0.98
