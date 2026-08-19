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


def _enabled(env_name: str, default: str = "1") -> bool:
    return os.getenv(env_name, default).lower() in {"1", "true", "yes", "on"}


class DeepSeekProvider:
    """Optional OpenAI-compatible DeepSeek adapter."""

    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.timeout = float(os.getenv("DEEPSEEK_TIMEOUT", "45"))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key) and _enabled("AI_DEEPSEEK_ENABLED")

    def complete(self, prompt: str) -> ProviderResult:
        return _openai_compatible("deepseek", self.api_key, self.base_url, self.model, self.timeout, prompt, self.enabled)


class GroqProvider:
    """Optional Groq OpenAI-compatible chat adapter."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.timeout = float(os.getenv("GROQ_TIMEOUT", "45"))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key) and _enabled("AI_GROQ_ENABLED")

    def complete(self, prompt: str) -> ProviderResult:
        return _openai_compatible("groq", self.api_key, self.base_url, self.model, self.timeout, prompt, self.enabled)


class GeminiProvider:
    """Optional Google Gemini generateContent adapter."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self.timeout = float(os.getenv("GEMINI_TIMEOUT", "45"))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key) and _enabled("AI_GEMINI_ENABLED")

    def complete(self, prompt: str) -> ProviderResult:
        if not self.enabled:
            return ProviderResult(False, "gemini", error="disabled")
        try:
            response = requests.post(
                f"{self.base_url}/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            candidates = data.get("candidates") or []
            parts = ((candidates[0] if candidates else {}).get("content") or {}).get("parts") or []
            text = "".join(str(part.get("text") or "") for part in parts).strip()
            return ProviderResult(bool(text), "gemini", text=text or None, error=None if text else "empty_response")
        except Exception as exc:
            return ProviderResult(False, "gemini", error=str(exc))


def _openai_compatible(name: str, api_key: str, base_url: str, model: str, timeout: float, prompt: str, enabled: bool) -> ProviderResult:
    if not enabled:
        return ProviderResult(False, name, error="disabled")
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0},
            timeout=timeout,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content")
        return ProviderResult(bool(text), name, text=str(text).strip() if text else None, error=None if text else "empty_response")
    except Exception as exc:
        return ProviderResult(False, name, error=str(exc))


deepseek = DeepSeekProvider()
groq = GroqProvider()
gemini = GeminiProvider()
