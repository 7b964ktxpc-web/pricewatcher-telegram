from product_offer_matcher import group_offers


def test_same_article_groups_and_picks_lowest_price():
    items = [
        {"title": "Nike Air Max 33", "article": "ABC", "brand": "Nike", "price": 2990, "source": "ozon"},
        {"title": "Nike Air Max детские 33", "article": "ABC", "brand": "Nike", "price": 2490, "source": "wildberries"},
    ]
    groups = group_offers(items)
    assert len(groups) == 1
    assert groups[0]["lowest_price"] == 2490
    assert groups[0]["offer_count"] == 2


def test_different_products_do_not_form_one_group():
    items = [
        {"title": "Nike Air Max 33", "article": "ABC", "brand": "Nike", "price": 2990},
        {"title": "Зимняя куртка детская", "article": "XYZ", "brand": "Reima", "price": 4990},
    ]
    groups = group_offers(items)
    assert len(groups) == 2
