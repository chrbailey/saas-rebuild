"""Correct HTTP contract and response parser for TypeSafe System One."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import time
from typing import Any, Callable, Mapping

from .questions import Question, to_wire
from .transport import TransportError, post_json


ENDPOINT = "https://api.typesafe.ai/v1/systemone"


class SystemOneError(RuntimeError):
    pass


@dataclass(frozen=True)
class Answer:
    type: str
    value: str | float
    probabilities: dict[str, float] | None
    confidence: float | None
    legend: dict[str, str] | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class Response:
    model: str
    answers: dict[str, Answer]
    usage: dict[str, int]
    request_id: str | None
    latency_ms: int
    raw: dict[str, Any]


def _probabilities(value: Any) -> dict[str, float] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise SystemOneError("answer probabilities must be an object")
    result = {str(key): float(probability) for key, probability in value.items()}
    if any(not math.isfinite(probability) or not 0 <= probability <= 1 for probability in result.values()):
        raise SystemOneError("answer probabilities must be finite values from 0 to 1")
    if result and not math.isclose(sum(result.values()), 1.0, rel_tol=1e-4, abs_tol=1e-4):
        raise SystemOneError("answer probabilities must sum to 1")
    return result


def parse_answer(question: dict[str, Any], raw: Any) -> Answer:
    if not isinstance(raw, dict):
        raise SystemOneError("answer must be an object")
    expected = question["type"]
    if raw.get("type") != expected:
        raise SystemOneError(f"answer type {raw.get('type')!r} does not match {expected!r}")
    if expected == "noul":
        value = float(raw.get("noul"))
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise SystemOneError("noul must be a finite value from 0 to 1")
        if "confidence" in raw:
            raise SystemOneError("noul answers must not contain confidence")
        return Answer(expected, value, None, None, None, raw)
    probabilities = _probabilities(raw.get("probabilities"))
    confidence = float(raw.get("confidence"))
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise SystemOneError("confidence must be a finite value from 0 to 1")
    if expected == "choice":
        choice = raw.get("choice")
        if choice not in question["criteria"] or probabilities is None or set(probabilities) != set(question["criteria"]):
            raise SystemOneError("choice answer does not match the declared criteria")
        return Answer(expected, str(choice), probabilities, confidence, None, raw)
    if expected == "score":
        score = float(raw.get("score"))
        legend = raw.get("legend")
        if not isinstance(legend, dict) or probabilities is None:
            raise SystemOneError("score answer requires legend and probabilities")
        expected_levels = {str(index) for index in range(len(question["criteria"]))}
        if set(probabilities) != expected_levels or set(legend) != expected_levels:
            raise SystemOneError("score answer levels do not match the declared criteria")
        if not 0 <= score <= len(question["criteria"]) - 1:
            raise SystemOneError("score is outside the declared level range")
        return Answer(expected, score, probabilities, confidence, {str(k): str(v) for k, v in legend.items()}, raw)
    raise SystemOneError(f"unsupported answer type: {expected!r}")


Transport = Callable[[str, dict[str, str], dict[str, Any], int], tuple[dict[str, Any], dict[str, str]]]


class SystemOne:
    def __init__(
        self,
        *,
        model: str = "jev-latest",
        endpoint: str = ENDPOINT,
        timeout: int = 60,
        api_key: str | None = None,
        transport: Transport = post_json,
    ) -> None:
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self._api_key = api_key
        self.transport = transport

    def _key(self) -> str:
        key = self._api_key or os.environ.get("TYPESAFE_API_KEY", "")
        if not key:
            raise SystemOneError("TYPESAFE_API_KEY is not set")
        return key

    def ask(self, state: Any, questions: Mapping[str, Question | Mapping[str, Any]]) -> Response:
        if not questions:
            raise SystemOneError("at least one question is required")
        wire_questions = {question_id: to_wire(question) for question_id, question in questions.items()}
        payload = {"state": state, "model": self.model, "questions": wire_questions}
        started = time.monotonic()
        try:
            body, headers = self.transport(
                self.endpoint,
                {"authorization": f"Bearer {self._key()}", "content-type": "application/json"},
                payload,
                self.timeout,
            )
        except TransportError as error:
            raise SystemOneError(str(error)) from error
        answers_raw = body.get("answers")
        if not isinstance(answers_raw, dict) or set(answers_raw) != set(wire_questions):
            raise SystemOneError("response answers do not match request question ids")
        model = body.get("model")
        if not isinstance(model, str) or not model:
            raise SystemOneError("response model is missing")
        usage = body.get("usage") or {}
        if not isinstance(usage, dict):
            raise SystemOneError("response usage must be an object")
        normalized_usage: dict[str, int] = {}
        for key in ("input_tokens", "output_tokens"):
            value = usage.get(key, 0)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SystemOneError(f"usage.{key} must be a non-negative integer")
            normalized_usage[key] = value
        answers = {
            question_id: parse_answer(wire_questions[question_id], answers_raw[question_id])
            for question_id in wire_questions
        }
        request_id = headers.get("x-request-id") or headers.get("request-id")
        latency_ms = round((time.monotonic() - started) * 1000)
        return Response(model, answers, normalized_usage, request_id, latency_ms, body)


def estimate_request_tokens(state: Any, questions: Mapping[str, Any]) -> int:
    rendered = json.dumps({"state": state, "questions": questions}, ensure_ascii=False)
    return math.ceil(len(rendered.encode("utf-8")) / 4)
