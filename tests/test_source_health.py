import time

from source_health import SourceHealthRegistry


def test_blocked_source_enters_cooldown():
    registry = SourceHealthRegistry(base_cooldown_s=10, max_cooldown_s=100)
    registry.record("wb", "blocked", "HTTP 429")
    assert not registry.allow("wb")
    snapshot = registry.snapshot()[0]
    assert snapshot["blocked"] == 1
    assert snapshot["last_status"] == "blocked"


def test_success_clears_cooldown():
    registry = SourceHealthRegistry(base_cooldown_s=10)
    registry.record("wb", "blocked", "HTTP 429")
    state = registry.state("wb")
    state.cooldown_until = time.monotonic() - 1
    registry.record("wb", "ok")
    assert registry.allow("wb")
    assert registry.state("wb").cooldown_until == 0
