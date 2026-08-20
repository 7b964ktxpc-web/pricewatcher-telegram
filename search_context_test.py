from search_context import is_follow_up, resolve_search_query


def test_short_follow_up_is_detected():
    assert is_follow_up("а подешевле?")
    assert is_follow_up("покажи ещё")
    assert is_follow_up("а для девочки?")


def test_full_search_is_not_rewritten():
    assert not is_follow_up("кроссовки мальчику 5 лет до 3000")


def test_follow_up_keeps_previous_search_context():
    history = [{"role": "user", "content": "кроссовки мальчику 5 лет до 3000"}]
    query = resolve_search_query("а подешевле?", history, [])
    assert "кроссовки мальчику 5 лет до 3000" in query
    assert "подешевле" in query
