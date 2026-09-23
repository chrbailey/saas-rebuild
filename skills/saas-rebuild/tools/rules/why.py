"""Deterministic rationale templates for matrix-owned decisions."""

from __future__ import annotations

from typing import Any, Iterable

from .matrix import Decision


TEMPLATES = {
    "MATRIX-RUNTIME-WORKAROUND": (
        "Observed runtime evidence and a documented workaround show the job is active; "
        "simplify the workflow around the workaround rather than remove it."
    ),
    "MATRIX-RUNTIME-CRITICAL": (
        "Observed runtime evidence supports a named critical business process, so the "
        "capability must be kept."
    ),
    "MATRIX-NEVER-ALL-TIME-NONCRITICAL": (
        "All-time runtime evidence records no use and no cited critical process depends "
        "on the capability, so it may be dropped after human sign-off."
    ),
    "MATRIX-UNKNOWN-OR-SHORT-WINDOW": (
        "The available runtime horizon cannot establish non-use, so the decision is "
        "deferred pending stronger evidence."
    ),
    "MATRIX-UNDEFINED": (
        "The default verdict matrix does not define this evidence combination; an analyst "
        "must decide and record the deviation."
    ),
}


def render_why(decision: Decision) -> str:
    return TEMPLATES[decision.rule_id]


def render_claim(decision: Decision, citations: Iterable[dict[str, Any]]) -> str:
    claims = [
        str(item.get("claim", "")).strip()
        for item in citations
        if item.get("evidence_id") in decision.evidence_ids and str(item.get("claim", "")).strip()
    ]
    return " ".join(claims) if claims else render_why(decision)


def render_reason(decision: Decision, citations: Iterable[dict[str, Any]]) -> str:
    ids = ", ".join(decision.evidence_ids) or "no resolved citations"
    return f"{render_why(decision)} Rule {decision.rule_id}; evidence: {ids}."
