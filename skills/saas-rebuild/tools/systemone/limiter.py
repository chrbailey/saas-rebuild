"""Rate, request-size, and live-validation budget guards."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time
from typing import Callable


class LimitExceeded(RuntimeError):
    pass


@dataclass
class BudgetGuard:
    max_calls: int
    max_input_tokens: int
    max_cost_usd: float | None = None
    price_per_million_input_tokens: float | None = None
    calls: int = 0
    input_tokens: int = 0

    def reserve(self, estimated_input_tokens: int) -> None:
        if estimated_input_tokens < 0:
            raise ValueError("estimated tokens must be non-negative")
        if self.calls + 1 > self.max_calls:
            raise LimitExceeded("live call budget exhausted")
        if self.input_tokens + estimated_input_tokens > self.max_input_tokens:
            raise LimitExceeded("live input-token budget exhausted")
        if self.max_cost_usd is not None:
            if self.price_per_million_input_tokens is None:
                raise LimitExceeded("a dollar cap requires an explicit verified price")
            projected = (
                (self.input_tokens + estimated_input_tokens)
                * self.price_per_million_input_tokens
                / 1_000_000
            )
            if projected > self.max_cost_usd:
                raise LimitExceeded("live dollar budget exhausted")

    def record(self, actual_input_tokens: int) -> None:
        self.calls += 1
        self.input_tokens += max(0, int(actual_input_tokens))
        if self.input_tokens > self.max_input_tokens:
            raise LimitExceeded("provider-reported usage exceeded the input-token budget")

    @property
    def estimated_cost_usd(self) -> float | None:
        if self.price_per_million_input_tokens is None:
            return None
        return self.input_tokens * self.price_per_million_input_tokens / 1_000_000


class RateLimiter:
    def __init__(
        self,
        *,
        requests_per_minute: int = 1_200,
        tokens_per_second: int = 250_000,
        max_request_tokens: int = 64_000,
        max_state_question_tokens: int = 32_000,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.tokens_per_second = tokens_per_second
        self.max_request_tokens = max_request_tokens
        self.max_state_question_tokens = max_state_question_tokens
        self.clock = clock
        self.sleep = sleep
        self._requests: deque[float] = deque()
        self._tokens: deque[tuple[float, int]] = deque()

    def acquire(self, request_tokens: int, state_question_tokens: int) -> None:
        if request_tokens > self.max_request_tokens:
            raise LimitExceeded("request exceeds the provider token limit")
        if state_question_tokens > self.max_state_question_tokens:
            raise LimitExceeded("state plus longest question exceeds the provider token limit")
        while True:
            now = self.clock()
            while self._requests and now - self._requests[0] >= 60:
                self._requests.popleft()
            while self._tokens and now - self._tokens[0][0] >= 1:
                self._tokens.popleft()
            token_total = sum(count for _, count in self._tokens)
            wait_request = 60 - (now - self._requests[0]) if len(self._requests) >= self.requests_per_minute else 0
            wait_tokens = 1 - (now - self._tokens[0][0]) if self._tokens and token_total + request_tokens > self.tokens_per_second else 0
            wait = max(wait_request, wait_tokens, 0)
            if wait <= 0:
                self._requests.append(now)
                self._tokens.append((now, request_tokens))
                return
            self.sleep(wait)
