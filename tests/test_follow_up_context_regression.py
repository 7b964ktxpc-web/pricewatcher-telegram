from search_context import is_follow_up, resolve_search_query


def test_follow_up_keeps_context_after_price_check_action():
    history = [
        {"role": "user", "content": "зимняя куртка девочке 7 лет размер 128 до 4000"},
        {"role": "user", "content": "Проверь цену"},
    ]
    query = resolve_search_query("а дешевле?", history, [])
    assert query.startswith("зимняя куртка девочке 7 лет размер 128 до 4000")
    assert "Проверь цену" not in query


def test_follow_up_with_short_pronoun_and_constraint_is_detected():
    assert is_follow_up("вот этот, но размер 128")
    assert is_follow_up("другого цвета")


def test_empty_context_falls_back_to_last_result():
    query = resolve_search_query("другой цвет", [], [{"title": "Nike Air Max"}])
    assert query == "Nike Air Max. Уточнение пользователя: другой цвет"
