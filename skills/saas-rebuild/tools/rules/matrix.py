"""The Phase 3 verdict matrix from SKILL.md, expressed as code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .derive import derive_usage, evidence_horizon, runtime_citations


@dataclass(frozen=True)
class Decision:
    verdict: str | None
    rule_id: str
    evidence_ids: tuple[str, ...]


def _ids(citations: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(sorted({str(item["evidence_id"]) for item in citations if item.get("evidence_id")}))


def _criticality_evidence(feature: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        citation
        for citation in feature.get("evidence", [])
        if "criticality" in citation.get("supports", [])
    ]


def decide(feature: dict[str, Any]) -> Decision:
    """Return only matrix-defined decisions; undefined cells remain ``None``."""

    runtime = runtime_citations(feature)
    critical = feature.get("criticality") == "critical" and bool(_criticality_evidence(feature))
    usage = derive_usage(feature)
    declared_usage = feature.get("usage")
    workaround = declared_usage in {"workaround-external", "workaround-internal"}

    if runtime and workaround:
        return Decision("SIMPLIFY", "MATRIX-RUNTIME-WORKAROUND", _ids(runtime))
    if runtime and usage in {"daily", "weekly", "rare"} and critical:
        evidence = runtime + _criticality_evidence(feature)
        return Decision("KEEP", "MATRIX-RUNTIME-CRITICAL", _ids(evidence))
    if usage == "never" and evidence_horizon(runtime) == "all-time" and not critical:
        return Decision("DROP", "MATRIX-NEVER-ALL-TIME-NONCRITICAL", _ids(runtime))
    if usage == "unknown" or (critical and evidence_horizon(runtime) == "window-bounded"):
        evidence = runtime + _criticality_evidence(feature)
        return Decision("DEFER", "MATRIX-UNKNOWN-OR-SHORT-WINDOW", _ids(evidence))
    return Decision(None, "MATRIX-UNDEFINED", _ids(runtime))
