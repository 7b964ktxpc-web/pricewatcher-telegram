from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

from ai_agent import plan_search
from ai_providers import deepseek


@dataclass(frozen=True)
class AgentSpec:
    name: str
    enabled_env: str
    handler: Callable[[str], Any]


class AIRouter:
    """Fail-soft multi-agent router with Qwen primary and optional DeepSeek validation."""

    def __init__(self) -> None:
        self.timeout = float(os.getenv("AI_ROUTER_TIMEOUT", "90"))

    def agents(self) -> list[AgentSpec]:
        return [
            AgentSpec("qwen_hf", "AI_QWEN_ENABLED", lambda request: plan_search(request)),
        ]

    def route(self, request: str) -> dict[str, Any]:
        request = request.strip()
        if not request:
            return {"ok": False, "agent": None, "error": "empty_request"}

        started = time.monotonic()
        attempts: list[dict[str, Any]] = []
        qwen_result: Any = None

        for spec in self.agents():
            if spec.name != "qwen_hf" and os.getenv(spec.enabled_env, "").lower() not in {"1", "true", "yes", "on"}:
                continue
            try:
                qwen_result = spec.handler(request)
                attempts.append({"agent": spec.name, "status": "ok", "elapsed_s": round(time.monotonic() - started, 3)})
                break
            except Exception as exc:
                attempts.append({"agent": spec.name, "status": "error", "error": str(exc)})
                qwen_result = None

        if qwen_result is None:
            qwen_result = plan_search(request)

        # DeepSeek is a validator/second opinion, never a hard dependency.
        if deepseek.enabled and time.monotonic() - started < self.timeout:
            validation_prompt = (
                "Проверь поисковый план для проекта Мама, дешевле!. "
                "Верни только JSON. Не меняй значения без необходимости. "
                f"Запрос покупателя: {request}\nПлан: {qwen_result}"
            )
            result = deepseek.complete(validation_prompt)
            attempts.append({"agent": result.provider, "status": "ok" if result.ok else "skipped", "error": result.error})
            if result.ok and result.text:
                return {
                    "ok": True,
                    "agent": "qwen_hf+deepseek_validator",
                    "result": qwen_result,
                    "validation": result.text,
                    "attempts": attempts,
                }

        return {"ok": True, "agent": "qwen_hf" if qwen_result else "deterministic", "result": qwen_result, "attempts": attempts}


router = AIRouter()
