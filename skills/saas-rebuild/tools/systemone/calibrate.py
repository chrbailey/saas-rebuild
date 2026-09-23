"""Calibration metrics and guarded threshold fitting (stdlib only)."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable


class CalibrationRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class IsotonicModel:
    boundaries: tuple[float, ...]
    values: tuple[float, ...]

    def predict(self, probability: float) -> float:
        for boundary, value in zip(self.boundaries, self.values):
            if probability <= boundary:
                return value
        return self.values[-1]


@dataclass(frozen=True)
class SprtResult:
    decision: str
    log_likelihood_ratio: float
    samples: int


def sprt(
    failures: Iterable[bool],
    *,
    acceptable_rate: float,
    unacceptable_rate: float,
    alpha: float = 0.05,
    beta: float = 0.10,
) -> SprtResult:
    """Sequentially accept, demote, or continue an engagement question.

    ``True`` means a reviewed answer failed. The lower hypothesis is the
    acceptable failure rate; the upper hypothesis is the rate at which the
    question must be demoted.
    """

    if not 0 < acceptable_rate < unacceptable_rate < 1:
        raise ValueError("SPRT rates must satisfy 0 < acceptable < unacceptable < 1")
    if not 0 < alpha < 1 or not 0 < beta < 1:
        raise ValueError("SPRT alpha and beta must be between 0 and 1")
    upper = math.log((1 - beta) / alpha)
    lower = math.log(beta / (1 - alpha))
    ratio = 0.0
    count = 0
    for failed in failures:
        count += 1
        ratio += (
            math.log(unacceptable_rate / acceptable_rate)
            if failed
            else math.log((1 - unacceptable_rate) / (1 - acceptable_rate))
        )
        if ratio >= upper:
            return SprtResult("demote", ratio, count)
        if ratio <= lower:
            return SprtResult("accept", ratio, count)
    return SprtResult("continue", ratio, count)


def _validate_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(records)
    roles: dict[str, set[str]] = {}
    for row in rows:
        if row.get("dataset_role") == "holdout-eval":
            raise CalibrationRefused("holdout-eval records cannot be used to fit calibration")
        if row.get("model_assist"):
            raise CalibrationRefused("model-assisted labels cannot be used to fit calibration")
        split_group = str(row.get("split_group", ""))
        roles.setdefault(split_group, set()).add(str(row.get("dataset_role", "")))
        if row.get("gold_source") not in {"system-of-record", "observed-ui"}:
            raise CalibrationRefused("calibration requires system-of-record or observed-ui gold")
    spanning = {key: value for key, value in roles.items() if len(value) > 1}
    if spanning:
        raise CalibrationRefused(f"split lineages span roles: {spanning}")
    return rows


def fit_isotonic(records: Iterable[dict[str, Any]]) -> IsotonicModel:
    rows = _validate_records(records)
    points = sorted((float(row["probability"]), int(bool(row["label"]))) for row in rows)
    if not points:
        raise CalibrationRefused("calibration needs at least one record")
    blocks: list[dict[str, float]] = []
    for probability, label in points:
        blocks.append({"lo": probability, "hi": probability, "sum": float(label), "count": 1.0})
        while len(blocks) >= 2:
            left, right = blocks[-2], blocks[-1]
            if left["sum"] / left["count"] <= right["sum"] / right["count"]:
                break
            blocks[-2:] = [{
                "lo": left["lo"],
                "hi": right["hi"],
                "sum": left["sum"] + right["sum"],
                "count": left["count"] + right["count"],
            }]
    return IsotonicModel(
        tuple(block["hi"] for block in blocks),
        tuple(block["sum"] / block["count"] for block in blocks),
    )


def brier(records: Iterable[dict[str, Any]]) -> float:
    rows = list(records)
    if not rows:
        raise ValueError("Brier score needs records")
    return sum((float(row["probability"]) - int(bool(row["label"]))) ** 2 for row in rows) / len(rows)


def expected_calibration_error(records: Iterable[dict[str, Any]], bins: int = 10) -> float:
    rows = list(records)
    if not rows or bins < 1:
        raise ValueError("ECE needs records and at least one bin")
    total = len(rows)
    result = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        bucket = [row for row in rows if lower <= float(row["probability"]) <= upper and (index == bins - 1 or float(row["probability"]) < upper)]
        if not bucket:
            continue
        confidence = sum(float(row["probability"]) for row in bucket) / len(bucket)
        accuracy = sum(int(bool(row["label"])) for row in bucket) / len(bucket)
        result += len(bucket) / total * abs(confidence - accuracy)
    return result


def _binomial_tail(successes: int, trials: int, probability: float) -> float:
    return sum(
        math.comb(trials, observed)
        * probability ** observed
        * (1 - probability) ** (trials - observed)
        for observed in range(successes, trials + 1)
    )


def clopper_pearson_lower(successes: int, trials: int, alpha: float = 0.05) -> float:
    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError("successes and trials are inconsistent")
    if successes == 0:
        return 0.0
    target = alpha / 2
    low, high = 0.0, successes / trials
    for _ in range(80):
        middle = (low + high) / 2
        if _binomial_tail(successes, trials, middle) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def choose_threshold(
    records: Iterable[dict[str, Any]],
    *,
    minimum_recall: float,
    minimum_lower_bound: float,
) -> float:
    rows = _validate_records(records)
    positives = sum(int(bool(row["label"])) for row in rows)
    if positives == 0:
        raise CalibrationRefused("threshold fitting needs positive examples")
    candidates = sorted({float(row["probability"]) for row in rows}, reverse=True)
    accepted: list[float] = []
    for threshold in candidates:
        caught = sum(
            1 for row in rows
            if bool(row["label"]) and float(row["probability"]) >= threshold
        )
        recall = caught / positives
        lower = clopper_pearson_lower(caught, positives)
        if recall >= minimum_recall and lower >= minimum_lower_bound:
            accepted.append(threshold)
    if not accepted:
        raise CalibrationRefused("no threshold meets the recall gate")
    return max(accepted)
