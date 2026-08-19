from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class SourceHealth:
    source: str
    successes: int = 0
    failures: int = 0
    blocked: int = 0
    cooldown_until: float = 0.0
    last_error: str | None = None
    last_status: str | None = None

    @property
    def available(self) -> bool:
        return time.monotonic() >= self.cooldown_until


class SourceHealthRegistry:
    """Process-local circuit breaker for unreliable public marketplace endpoints."""

    def __init__(self, base_cooldown_s: float = 60.0, max_cooldown_s: float = 1800.0):
        self.base = max(1.0, base_cooldown_s)
        self.maximum = max(self.base, max_cooldown_s)
        self._states: dict[str, SourceHealth] = {}

    def state(self, source: str) -> SourceHealth:
        return self._states.setdefault(source, SourceHealth(source))

    def allow(self, source: str) -> bool:
        return self.state(source).available

    def record(self, source: str, status: str, error: str | None = None) -> None:
        state = self.state(source)
        state.last_status = status
        state.last_error = error
        if status == "ok":
            state.successes += 1
            state.cooldown_until = 0.0
            return
        if status in {"disabled", "not_configured", "html_only"}:
            return
        state.failures += 1
        if status == "blocked":
            state.blocked += 1
            exponent = min(state.blocked - 1, 5)
            cooldown = min(self.base * (2**exponent), self.maximum)
            state.cooldown_until = time.monotonic() + cooldown

    def snapshot(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        return [
            {
                "source": state.source,
                "available": now >= state.cooldown_until,
                "successes": state.successes,
                "failures": state.failures,
                "blocked": state.blocked,
                "cooldown_seconds": max(0.0, round(state.cooldown_until - now, 1)),
                "last_status": state.last_status,
                "last_error": state.last_error,
            }
            for state in self._states.values()
        ]


HEALTH = SourceHealthRegistry(
    base_cooldown_s=float(os.getenv("SOURCE_COOLDOWN_BASE", "60")),
    max_cooldown_s=float(os.getenv("SOURCE_COOLDOWN_MAX", "1800")),
)


def source_health_snapshot() -> list[dict[str, Any]]:
    return HEALTH.snapshot()
