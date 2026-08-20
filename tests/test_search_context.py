from search_context import is_follow_up, resolve_search_query


def test_follow_up_after_callback_uses_real_search_context():
    history = [
        {"role": "user", "content": "кроссовки мальчику 6 лет размер 30 до 2500"},
        {"role": "user", "content": "Найди дешевле"},
    ]
    query = resolve_search_query("другого цвета", history, [])
    assert query.startswith("кроссовки мальчику 6 лет размер 30 до 2500")
    assert "Найди дешевле" not in query


def test_pronoun_follow_up_is_detected():
    assert is_follow_up("вот этот, но размер 128")


def test_non_follow_up_remains_unchanged():
    assert resolve_search_query("красные кроссовки мальчику 6 лет", [], []) == "красные кроссовки мальчику 6 лет"
