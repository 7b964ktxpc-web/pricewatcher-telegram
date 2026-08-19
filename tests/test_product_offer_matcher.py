from product_offer_matcher import group_offers, similarity


def test_similarity_is_high_for_same_product():
    assert similarity('Кроссовки детские Nike Air Max 30', 'Nike Air Max детские кроссовки 30') >= 0.68


def test_group_offers_selects_lowest_price():
    groups = group_offers([
        {'title': 'Кроссовки детские Nike Air Max 30', 'price': 2490, 'source': 'ozon'},
        {'title': 'Nike Air Max детские кроссовки 30', 'price': 2190, 'source': 'detmir'},
        {'title': 'Куртка зимняя детская', 'price': 4990, 'source': 'shop'},
    ])
    nike = next(g for g in groups if g['offer_count'] == 2)
    assert nike['lowest_price'] == 2190
    assert nike['best_offer']['source'] == 'detmir'
