"""Derive numeric and temporal signals without model judgment."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable


RUNTIME_PLANES = frozenset({"transactional", "telemetry", "integration-inventory"})
COUNT_METRICS = frozenset({
    "execution-count", "event-count", "record-count", "run-count", "transaction-count"
})


def runtime_citations(feature: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        citation
        for citation in feature.get("evidence", [])
        if citation.get("evidence_class") == "runtime"
        and citation.get("plane") in RUNTIME_PLANES
        and "usage" in citation.get("supports", [])
    ]


def evidence_horizon(citations: Iterable[dict[str, Any]]) -> str | None:
    """Return the strongest declared horizon without interpreting dates."""

    kinds = {
        citation.get("coverage", {}).get("kind")
        for citation in citations
    }
    for kind in ("all-time", "window-bounded", "point-in-time", "not-applicable"):
        if kind in kinds:
            return kind
    return None


def _numeric_measure(citation: dict[str, Any]) -> float | None:
    measure = citation.get("measure")
    if not isinstance(measure, dict) or measure.get("metric") not in COUNT_METRICS:
        return None
    value = measure.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def derive_usage(feature: dict[str, Any]) -> str:
    """Derive only conclusions supported by structured runtime measures.

    Text never supplies a count.  Positive runtime counts establish use but do
    not guess cadence; zero establishes ``never`` only with all-time coverage.
    Everything else stays unknown for an analyst to resolve.
    """

    citations = runtime_citations(feature)
    measured = [(citation, _numeric_measure(citation)) for citation in citations]
    if any(value is not None and value > 0 for _, value in measured):
        declared = feature.get("usage")
        return declared if declared in {"daily", "weekly", "rare"} else "rare"
    if any(
        value == 0 and citation.get("coverage", {}).get("kind") == "all-time"
        for citation, value in measured
    ):
        return "never"
    return "unknown"


def script_liveness(feature: dict[str, Any]) -> str:
    """Classify script activity from structured execution counts."""

    if feature.get("kind") != "automation":
        return "not-applicable"
    usage = derive_usage(feature)
    if usage == "never":
        return "never-executed"
    if usage in {"daily", "weekly", "rare"}:
        return "executed"
    return "unknown"


def edge_runtime_status(edge: dict[str, Any], citations: dict[str, dict[str, Any]]) -> str:
    """Derive whether a graph edge has positive, zero, or unknown runtime proof."""

    values: list[tuple[dict[str, Any], float | None]] = []
    for evidence_id in edge.get("evidence_ids", []):
        citation = citations.get(evidence_id)
        if citation and citation.get("evidence_class") == "runtime":
            values.append((citation, _numeric_measure(citation)))
    if any(value is not None and value > 0 for _, value in values):
        return "observed"
    if any(
        value == 0 and citation.get("coverage", {}).get("kind") == "all-time"
        for citation, value in values
    ):
        return "not-observed-all-time"
    return "unknown"


def window_days(measure: dict[str, Any]) -> int | None:
    """Compute an inclusive calendar window in code, never in Jev."""

    try:
        start = date.fromisoformat(str(measure["window_start"])[:10])
        end = date.fromisoformat(str(measure["window_end"])[:10])
    except (KeyError, TypeError, ValueError):
        return None
    return (end - start).days + 1 if end >= start else None


def normalize_timestamp(value: str) -> str:
    """Validate and normalize a timestamp used by deterministic records."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.isoformat().replace("+00:00", "Z")
