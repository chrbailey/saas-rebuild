"""Evaluate explicitly calibrated, model-bound raise-only policies."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .client import Answer
from .questions import question_hash


@dataclass(frozen=True)
class Effect:
    effect: str
    calibrated_p: float | None = None
    threshold_set_id: str | None = None


def evaluate(
    item: dict[str, Any], answer: Answer, *, mode: str, model: str,
    catalog_version: str, policy: dict[str, Any] | None,
    canary_model: str | None = None, twin: Answer | None = None,
) -> Effect:
    if mode == "shadow":
        return Effect("none")
    authority = item.get("authority", "prioritize")
    if authority not in {"flag", "veto", "reject"}:
        return Effect(authority if authority in {"prioritize", "suggest"} else "none")
    if policy is None:
        return Effect("prioritize")
    if not isinstance(policy, dict):
        raise ValueError("thresholds require a calibrated policy, not a bare number")
    if (
        policy.get("model") != model or canary_model != model
        or policy.get("question_hash") != question_hash(item["question"])
        or policy.get("catalog_version") != catalog_version
        or not policy.get("approved_by") or not policy.get("validation_ref")
        or not policy.get("id")
    ):
        return Effect("prioritize")

    def probability(value: Answer) -> float:
        if value.type == "noul":
            positive = policy.get("positive")
            if positive not in {"yes", "no"}:
                raise ValueError("Noul policy requires positive=yes or no")
            raw = float(value.value)
            return raw if positive == "yes" else 1 - raw
        if value.type == "choice":
            options = policy.get("positive_options")
            if not isinstance(options, list) or not options or len(set(options)) != len(options):
                raise ValueError("Choice policy requires unique positive_options")
            if not value.probabilities or set(options) - set(value.probabilities):
                raise ValueError("policy options do not match the answer")
            return sum(value.probabilities[option] for option in options)
        raise ValueError("Score authority is disabled until separately validated")

    fit = policy.get("isotonic") or {}
    boundaries, values = fit.get("boundaries", []), fit.get("values", [])
    if (
        not boundaries or len(boundaries) != len(values)
        or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1 for x in boundaries + values)
        or any(a >= b for a, b in zip(boundaries, boundaries[1:]))
        or values != sorted(values)
    ):
        raise ValueError("policy requires a finite monotone isotonic fit")
    threshold, band = policy.get("threshold"), policy.get("hysteresis", 0.02)
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1 for x in (threshold, band)):
        raise ValueError("threshold and hysteresis must be probabilities")

    def calibrated(value: Answer) -> float:
        raw = probability(value)
        return next((p for boundary, p in zip(boundaries, values) if raw <= boundary), values[-1])

    p = calibrated(answer)
    if authority == "veto" and (twin is None or twin.type != answer.type or calibrated(twin) < threshold - band):
        return Effect("prioritize", p, policy["id"])
    # The uncertainty band always adds review, never silently clears an item.
    effect = authority if p >= threshold - band else "prioritize"
    return Effect(effect, p, policy["id"])
