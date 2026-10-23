"""Catalog signals and legacy calibration types (routing compatibility only)."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from .calibrate import IsotonicModel
from .client import Answer

# Uncalibrated signals only ever route work; this cutoff never gates a veto,
# flag, or reject, which require a fitted threshold on eligible gold.
ROUTING_CUTOFF = 0.5


@dataclass(frozen=True)
class CalibratedThreshold:
    """A fitted threshold, bound to the exact question text it was fitted on."""

    question_hash: str
    model: IsotonicModel
    threshold: float


@dataclass(frozen=True)
class ThresholdSet:
    threshold_set_id: str
    entries: Mapping[str, CalibratedThreshold]


def _signal(
    catalog_item: dict[str, Any],
    answer: Answer,
    context: Mapping[str, Any] | None = None,
) -> float | None:
    """Probability that the answer is the one the question's authority acts on.

    A noul answer is already that probability. A choice answer counts only the
    options its catalog entry names: a fixed ``trigger``, or under ``compare``
    the options that contradict the target's declared value. Without either,
    or when that declared value is absent or unmapped, there is no signal, so
    the question cannot act on anything.
    """

    if answer.type == "noul":
        return float(answer.value)
    if answer.type != "choice" or answer.probabilities is None:
        return None
    options = catalog_item.get("trigger")
    compare = catalog_item.get("compare")
    if compare is not None:
        declared = (context or {}).get(compare["against"])
        options = compare["contradicts"].get(declared) if isinstance(declared, str) else None
        if options is not None and not options:
            return 0.0
    if not options:
        return None
    return min(1.0, sum(answer.probabilities.get(option, 0.0) for option in options))
