from main import summarize_feed_readiness


def test_readiness_normalizes_structured_feed_report():
    feeds = {
        "checked": 2,
        "configured": ["simaland"],
        "results": [
            {"name": "simaland", "configured": True},
            {"name": "detmir", "configured": False},
        ],
    }

    result = summarize_feed_readiness(feeds)

    assert result["configured"] == 1
    assert result["total"] == 2
    assert result["items"] is feeds


def test_readiness_remains_compatible_with_legacy_feed_list():
    feeds = [
        {"name": "simaland", "configured": True},
        {"name": "detmir", "configured": False},
    ]

    result = summarize_feed_readiness(feeds)

    assert result["configured"] == 1
    assert result["total"] == 2
    assert result["items"] is feeds
