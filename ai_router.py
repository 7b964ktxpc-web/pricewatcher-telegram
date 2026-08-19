from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

from ai_agent import plan_search


@dataclass(frozen=True)
class AgentSpec:
    name: str
    enabled_env: str
    handler: Callable[[str], str]


class AIRouter:
    """Fail-soft multi-agent router: Qwen is primary, other agents are optional fallbacks."""

    def __init__(self) -> None:
        self.timeout = float(os.getenv("AI_ROUTER_TIMEOUT", "90"))
        self.max_attempts = max(1, int(os.getenv("AI_ROUTER_MAX_ATTEMPTS", "3")))

    @staticmethod
    def _enabled(env_name: str) -> bool:
        return os.getenv(env_name, "").strip().lower() in {"1", "true", "yes", "on"}

    def agents(self) -> list[AgentSpec]:
        return [
            AgentSpec("qwen_hf", "AI_QWEN_ENABLED", lambda request: str(plan_search(request))),
        ]

    def route(self, request: str) -> dict[str, Any]:
        request = request.strip()
        if not request:
            return {"ok": False, "agent": None, "error": "empty_request"}

        started = time.monotonic()
        attempts: list[dict[str, Any]] = []
        for spec in self.agents():
            # Qwen is available by default; optional agents must opt in.
            if spec.name != "qwen_hf" and not self._enabled(spec.enabled_env):
                continue
            try:
                result = spec.handler(request)
                elapsed = round(time.monotonic() - started, 3)
                attempts.append({"agent": spec.name, "status": "ok", "elapsed_s": elapsed})
                if isinstance(result, str):
                    return {"ok": True, "agent": spec.name, "result": result, "attempts": attempts}
                return {"ok": True, "agent": spec.name, "result": result, "attempts": attempts}
            except Exception as exc:
                attempts.append({"agent": spec.name, "status": "error", "error": str(exc)})
                if time.monotonic() - started >= self.timeout:
                    break

        # Deterministic fallback keeps the search engine usable without any AI provider.
        return {"ok": True, "agent": "deterministic", "result": plan_search(request), "attempts": attempts}


router = AIRouter()
