"""Deterministic fakes for contract and failure-path tests."""

from __future__ import annotations

from collections import deque
from typing import Any

from .client import SystemOne


class FakeTransport:
    def __init__(self, responses: list[tuple[dict[str, Any], dict[str, str]]] | None = None) -> None:
        self.responses = deque(responses or [])
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        self.calls.append({
            "url": url,
            "headers": {key: "[REDACTED]" if key.lower() == "authorization" else value for key, value in headers.items()},
            "payload": payload,
            "timeout": timeout,
        })
        if not self.responses:
            raise AssertionError("FakeTransport has no queued response")
        return self.responses.popleft()


class FakeSystemOne(SystemOne):
    def __init__(self, responses: list[tuple[dict[str, Any], dict[str, str]]]) -> None:
        self.fake_transport = FakeTransport(responses)
        super().__init__(api_key="fake-test-key", transport=self.fake_transport)
