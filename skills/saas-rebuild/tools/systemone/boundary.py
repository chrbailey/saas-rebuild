"""Fail-closed data-boundary tickets for every System One call."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


DATA_CLASSES = ("public", "internal", "confidential", "restricted")


class BoundaryRefused(RuntimeError):
    """The requested call is outside an approved endpoint boundary."""


@dataclass(frozen=True)
class BoundaryTicket:
    endpoint_id: str
    endpoint: str
    purpose: str
    allowed_data_classes: tuple[str, ...]
    approved_by: str
    approved_at: str


def _status(value: Any) -> str:
    return value.get("status", "unknown") if isinstance(value, dict) else "unknown"


def regulated_data(teardown: dict[str, Any]) -> tuple[bool, bool]:
    """Return (contains_phi, contains_eu_personal_data), failing closed.

    Only an explicit "no" clears a category; an absent declaration or
    "unknown" counts as present, so the BAA and transfer gates engage.
    """

    declared = (teardown.get("data_boundary") or {}).get("regulated_data") or {}
    return declared.get("phi") != "no", declared.get("eu_personal_data") != "no"


def open_ticket(
    teardown: dict[str, Any],
    endpoint_id: str,
    purpose: str,
    data_classes: Iterable[str],
    *,
    contains_phi: bool = False,
    contains_eu_personal_data: bool = False,
) -> BoundaryTicket:
    boundary = teardown.get("data_boundary") or {}
    preflight = {item.get("id"): item for item in teardown.get("preflight", [])}
    review = preflight.get("model-vendor-review")
    if not review or review.get("status") != "ready":
        raise BoundaryRefused("model-vendor-review preflight is not ready")

    endpoints = boundary.get("model_endpoints") or []
    endpoint = next((item for item in endpoints if item.get("id") == endpoint_id), None)
    if endpoint is None:
        raise BoundaryRefused(f"model endpoint {endpoint_id!r} is not declared")
    if endpoint.get("endpoint") != "https://api.typesafe.ai/v1/systemone":
        raise BoundaryRefused("unapproved System One endpoint")
    if purpose not in endpoint.get("purposes", []):
        raise BoundaryRefused(f"purpose {purpose!r} is not approved")

    sent = set(data_classes)
    if not sent:
        sent = {"restricted"}
    unknown = sent - set(DATA_CLASSES)
    if unknown:
        raise BoundaryRefused(f"unknown data classes: {sorted(unknown)}")
    global_allowed = set(boundary.get("allowed_data_classes") or [])
    endpoint_allowed = set(endpoint.get("allowed_data_classes") or [])
    refused = sent - global_allowed | sent - endpoint_allowed
    if refused:
        raise BoundaryRefused(f"data classes are outside the approved boundary: {sorted(refused)}")
    if "restricted" in sent and _status(endpoint.get("zdr")) != "in-force":
        raise BoundaryRefused("restricted data requires ZDR in force")
    if contains_phi and _status(endpoint.get("baa")) != "in-force":
        raise BoundaryRefused("PHI requires a BAA in force")
    if contains_eu_personal_data and not endpoint.get("transfer_mechanism"):
        raise BoundaryRefused("EU personal data requires a recorded transfer mechanism")

    return BoundaryTicket(
        endpoint_id=endpoint_id,
        endpoint=endpoint["endpoint"],
        purpose=purpose,
        allowed_data_classes=tuple(sorted(sent)),
        approved_by=endpoint["approved_by"],
        approved_at=endpoint["approved_at"],
    )
