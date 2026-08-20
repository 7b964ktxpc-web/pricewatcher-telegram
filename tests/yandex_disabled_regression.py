from agent_router import ALLOWED_SOURCES
from feed_adapters import FEED_ADAPTERS
from providers import PROVIDERS


def test_yandex_market_is_not_a_configured_source():
    assert "yandex_market" not in ALLOWED_SOURCES
    assert "yandex_market_feed" not in FEED_ADAPTERS
    assert "yandex_market" not in PROVIDERS
    assert "yandex-market-public" not in {getattr(provider, "name", "") for provider in PROVIDERS.values()}
