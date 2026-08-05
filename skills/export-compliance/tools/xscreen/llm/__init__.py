"""Pluggable model backends.

Three reasons this is an interface rather than a hard dependency on one API:

1. **On-premise is the point.** A company replacing a screening SaaS often
   cannot send counterparty names to a third-party endpoint at all. The
   OpenAI-compatible backend talks to vLLM, Ollama, LM Studio or any local
   server, so the whole pipeline runs inside the network boundary.
2. **Cross-model validation is a real control.** Running the adjudication on
   one model family and the critic on another catches shared failure modes
   that a self-review cannot. `xscreen adjudicate --model A` followed by
   `xscreen critic --model B` is the supported pattern.
3. **Degradation must be safe.** When no backend is configured, the offline
   backend returns explicit "no machine adjudication" results and every case
   routes to a human. Missing model access must never look like a clear.

Backends are constructed from environment variables so no credential ever
lands in a config file inside the repository.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class BackendError(RuntimeError):
    """Transport, auth or protocol failure. Never treated as a model verdict."""


class Backend(Protocol):
    name: str

    def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> dict[str, Any]:
        """Return parsed JSON. Raise BackendError on any failure."""
        ...


def _ssl_ctx() -> ssl.SSLContext:
    ca = (
        os.environ.get("XSCREEN_CA_BUNDLE")
        or os.environ.get("REQUESTS_CA_BUNDLE")
        or os.environ.get("SSL_CERT_FILE")
    )
    if ca and os.path.exists(ca):
        return ssl.create_default_context(cafile=ca)
    return ssl.create_default_context()


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """Parse a JSON object out of a model response.

    Raises BackendError rather than returning a partial dict: a response that
    cannot be parsed is an infrastructure error, and an infrastructure error
    must never be routed as a verdict.
    """
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_BLOCK.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise BackendError(f"model returned unparseable JSON: {e}") from e
    raise BackendError("model response contained no JSON object")


def _post(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 - every transport failure is a BackendError
        raise BackendError(f"{type(e).__name__}: {e}") from e


@dataclass
class AnthropicBackend:
    model: str = "claude-sonnet-5"
    api_key: str = ""
    base_url: str = "https://api.anthropic.com"
    timeout: int = 120

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.name = f"anthropic:{self.model}"
        if not self.api_key:
            raise BackendError("ANTHROPIC_API_KEY is not set")

    def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> dict[str, Any]:
        data = _post(
            f"{self.base_url}/v1/messages",
            {
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": 0,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            self.timeout,
        )
        parts = data.get("content") or []
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        return extract_json(text)


@dataclass
class OpenAICompatBackend:
    """Any OpenAI chat-completions compatible endpoint.

    Covers self-hosted vLLM / Ollama / LM Studio / llama.cpp as well as hosted
    providers that speak the same protocol (Moonshot/Kimi, DeepSeek, Together,
    Groq). Set XSCREEN_LLM_BASE_URL and XSCREEN_LLM_MODEL.
    """

    model: str = ""
    api_key: str = ""
    base_url: str = ""
    timeout: int = 180

    def __post_init__(self) -> None:
        self.base_url = (self.base_url or os.environ.get("XSCREEN_LLM_BASE_URL", "")).rstrip("/")
        self.model = self.model or os.environ.get("XSCREEN_LLM_MODEL", "")
        self.api_key = self.api_key or os.environ.get("XSCREEN_LLM_API_KEY", "not-needed")
        self.name = f"openai-compat:{self.model or 'unset'}"
        if not self.base_url or not self.model:
            raise BackendError(
                "XSCREEN_LLM_BASE_URL and XSCREEN_LLM_MODEL must both be set"
            )

    def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> dict[str, Any]:
        data = _post(
            f"{self.base_url}/chat/completions",
            {"content-type": "application/json", "authorization": f"Bearer {self.api_key}"},
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            self.timeout,
        )
        choices = data.get("choices") or []
        if not choices:
            raise BackendError(f"no choices in response: {str(data)[:200]}")
        return extract_json(choices[0].get("message", {}).get("content", ""))


@dataclass
class OfflineBackend:
    """No model available. Every case escalates to a human, loudly."""

    name: str = "offline"

    def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> dict[str, Any]:
        raise BackendError(
            "no model backend configured -- set XSCREEN_LLM_BASE_URL/MODEL or "
            "ANTHROPIC_API_KEY, or run with --no-llm to route every candidate "
            "to human review"
        )


def get_backend(spec: str | None = None) -> Backend:
    """Resolve a backend from `spec` or the environment.

    spec forms: "anthropic", "anthropic:<model>", "openai", "openai:<model>",
    "offline". Defaults to XSCREEN_BACKEND, then to whatever is configured.
    """
    spec = (spec or os.environ.get("XSCREEN_BACKEND") or "").strip()
    kind, _, model = spec.partition(":")
    kind = kind.lower()

    if kind == "offline":
        return OfflineBackend()
    if kind == "anthropic":
        return AnthropicBackend(model=model or "claude-sonnet-5")
    if kind in ("openai", "openai-compat", "local", "kimi"):
        return OpenAICompatBackend(model=model or "")
    if not spec:
        if os.environ.get("XSCREEN_LLM_BASE_URL"):
            return OpenAICompatBackend()
        if os.environ.get("ANTHROPIC_API_KEY"):
            return AnthropicBackend()
        return OfflineBackend()
    raise BackendError(f"unknown backend spec {spec!r}")
