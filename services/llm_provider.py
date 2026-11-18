"""Provider adapter: Gemini, Anthropic, and a clearly labelled MOCK mode.

Every call returns the provider's own usage metadata. Token counts are never
estimated: if the provider does not report them they are left as None.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

DEFAULT_MODELS = {
    "gemini": os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
    "mock": "mock-no-model",
}


@dataclass
class LLMResult:
    text: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    thinking_tokens: Optional[int]
    tokens_reported: bool
    duration_s: float


class LLMError(Exception):
    pass


class Provider:
    name = "base"
    is_mock = False

    def __init__(self, model: str, api_key: Optional[str] = None, timeout_s: float = 45):
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s

    def complete(self, system: str, user: str, max_tokens: int = 4000) -> LLMResult:
        raise NotImplementedError


class GeminiProvider(Provider):
    name = "gemini"
    # another small model tried only if the primary is overloaded (503/429); the trace records which one answered
    fallbacks = [m for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.1-flash-lite").split(",") if m]

    def __init__(self, model, api_key=None, timeout_s=45):
        super().__init__(model, api_key, timeout_s)
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise LLMError("Missing GEMINI_API_KEY")
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))

    def complete(self, system, user, max_tokens=4000):
        t = self._types
        cfg = dict(system_instruction=system, temperature=0, max_output_tokens=max_tokens,
                   response_mime_type="application/json")
        # Disable hidden "thinking" on models that support a budget: fewer tokens, faster.
        if "2.5" in self.model and "pro" not in self.model:
            cfg["thinking_config"] = t.ThinkingConfig(thinking_budget=0)
        t0 = time.time()
        resp = self._client.models.generate_content(model=self.model, contents=user,
                                                    config=t.GenerateContentConfig(**cfg))
        dt = time.time() - t0
        um = getattr(resp, "usage_metadata", None)
        inp = getattr(um, "prompt_token_count", None) if um else None
        out = getattr(um, "candidates_token_count", None) if um else None
        think = getattr(um, "thoughts_token_count", None) if um else None
        return LLMResult(resp.text or "", inp, out, think, inp is not None and out is not None, dt)


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model, api_key=None, timeout_s=45):
        super().__init__(model, api_key, timeout_s)
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("Missing ANTHROPIC_API_KEY")
        import anthropic

        self._client = anthropic.Anthropic(api_key=key, timeout=timeout_s, max_retries=0)

    def complete(self, system, user, max_tokens=4000):
        t0 = time.time()
        resp = self._client.messages.create(model=self.model, max_tokens=max_tokens, system=system,
                                            temperature=0, messages=[{"role": "user", "content": user}])
        dt = time.time() - t0
        text = "".join(getattr(b, "text", "") for b in resp.content)
        u = resp.usage
        return LLMResult(text, u.input_tokens, u.output_tokens, None, True, dt)


class MockProvider(Provider):
    """NOT a model. Returns an empty extraction so the UI can be exercised without a key.
    Trace entries are flagged is_mock and carry no token counts."""

    name = "mock"
    is_mock = True

    def complete(self, system, user, max_tokens=4000):
        return LLMResult('{"messages":[],"claims":[]}', None, None, None, False, 0.0)


def make_provider(kind: str, model: Optional[str] = None, api_key: Optional[str] = None,
                  timeout_s: float = 45) -> Provider:
    kind = (kind or "gemini").lower()
    model = model or DEFAULT_MODELS.get(kind, "")
    if kind == "gemini":
        return GeminiProvider(model, api_key, timeout_s)
    if kind == "anthropic":
        return AnthropicProvider(model, api_key, timeout_s)
    return MockProvider(model or "mock-no-model")


def is_retryable(err: Exception) -> bool:
    s = f"{type(err).__name__} {err}".lower()
    return any(x in s for x in ("429", "rate", "quota", "timeout", "timed out", "503", "500", "overloaded",
                                "unavailable", "connection", "resource_exhausted", "deadline"))
