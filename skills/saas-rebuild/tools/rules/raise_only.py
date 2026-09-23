"""Monotone application of model annotations.

Jev may add review or hold a DROP as DEFER.  It never records a DROP, clears
review, approves sharing, removes an edge, or declares a replay equivalent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .matrix import Decision


ALLOWED_EFFECTS = frozenset({"flag", "veto", "reject", "prioritize", "suggest", "none"})


@dataclass(frozen=True)
class RaisedDecision:
    decision: Decision
    review_reasons: tuple[str, ...]
    annotation_ids: tuple[str, ...]


def apply_raise(
    baseline: Decision,
    annotations: Iterable[dict[str, Any]],
    baseline_review: Iterable[str] = (),
) -> RaisedDecision:
    review = set(baseline_review)
    consumed: list[str] = []
    verdict = baseline.verdict
    rule_id = baseline.rule_id

    for annotation in annotations:
        effect = annotation.get("effect", "none")
        if effect not in ALLOWED_EFFECTS:
            raise ValueError(f"unsupported annotation effect: {effect!r}")
        annotation_id = annotation.get("annotation_id")
        if annotation_id:
            consumed.append(str(annotation_id))
        if effect != "none":
            review.add(f"jev:{effect}:{annotation.get('question_id', 'unknown')}")
        if effect == "veto" and verdict == "DROP":
            verdict = "DEFER"
            rule_id = "RAISE-JEV-VETO"

    raised = Decision(verdict, rule_id, baseline.evidence_ids)
    return RaisedDecision(raised, tuple(sorted(review)), tuple(sorted(set(consumed))))
