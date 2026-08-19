from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class ProviderResult:
    ok: bool
    provider: str
    text: str | None = None
    error: str | None = None


class DeepSeekProvider:
    """Optional OpenAI-compatible DeepSeek adapter.

    Disabled unless DEEPSEEK_API_KEY is configured. This keeps the default
    deployment free of mandatory paid AI traffic while allowing DeepSeek to
    act as a second planner/validator.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.timeout = float(os.getenv("DEEPSEEK_TIMEOUT", "45"))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key) and os.getenv("AI_DEEPSEEK_ENABLED", "1").lower() in {"1", "true", "yes", "on"}

    def complete(self, prompt: str) -> ProviderResult:
        if not self.enabled:
            return ProviderResult(False, "deepseek", error="disabled")
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content")
            return ProviderResult(bool(text), "deepseek", text=text, error=None if text else "empty_response")
        except Exception as exc:
            return ProviderResult(False, "deepseek", error=str(exc))


deepseek = DeepSeekProvider()
