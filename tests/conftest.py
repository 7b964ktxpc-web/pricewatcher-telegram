"""Shared pytest configuration for the parser test suite."""

import pytest


@pytest.fixture(autouse=True)
def isolate_source_health():
    """Keep the process-global circuit breaker isolated between tests."""
    from providers import HEALTH
    HEALTH.reset()
    yield
    HEALTH.reset()
