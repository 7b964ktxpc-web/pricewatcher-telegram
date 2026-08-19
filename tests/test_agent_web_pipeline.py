from agent_web_pipeline import _normalise_page


def test_normalise_page_marks_web_results_as_discovery_only():
    result = _normalise_page(
        {
            "title": "Кроссовки детские",
            "url": "https://pepper.ru/deal/123",
            "final_url": "https://pepper.ru/deal/123",
            "source": "pepper",
            "status": 200,
            "text": "товар",
        },
        "кроссовки мальчику",
    )
    assert result["source"] == "pepper"
    assert result["discovery_only"] is True
    assert result["page_text_available"] is True


def test_normalise_page_falls_back_to_query_and_url():
    result = _normalise_page({}, "детская куртка")
    assert result["title"] == "детская куртка"
    assert result["url"] is None
    assert result["discovery_only"] is True
