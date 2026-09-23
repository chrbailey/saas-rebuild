"""Frozen canary comparison and authority demotion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CanaryResult:
    passed: bool
    reasons: tuple[str, ...]
    authority: str


def compare_canary(
    expected: dict[str, Any],
    actual: dict[str, Any],
    *,
    expected_model: str,
    actual_model: str,
) -> CanaryResult:
    reasons: list[str] = []
    if actual_model != expected_model:
        reasons.append(f"model drift: expected {expected_model}, got {actual_model}")
    for question_id, expected_answer in expected.items():
        if question_id not in actual:
            reasons.append(f"missing canary answer: {question_id}")
        elif actual[question_id] != expected_answer:
            reasons.append(f"canary answer drift: {question_id}")
    return CanaryResult(not reasons, tuple(reasons), "configured" if not reasons else "prioritize-only")


def agreement_rate(repeats: list[dict[str, Any]]) -> dict[str, float]:
    if not repeats:
        return {}
    question_ids = set.intersection(*(set(item) for item in repeats))
    result: dict[str, float] = {}
    for question_id in sorted(question_ids):
        values = [item[question_id] for item in repeats]
        winner = max(set(map(str, values)), key=lambda value: sum(str(item) == value for item in values))
        result[question_id] = sum(str(item) == winner for item in values) / len(values)
    return result
