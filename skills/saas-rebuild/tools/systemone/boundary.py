"""Fail-closed data-boundary tickets for every System One call."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
    matches = [item for item in endpoints if item.get("id") == endpoint_id]
    if len(matches) > 1:
        raise BoundaryRefused("model endpoint id is duplicated")
    endpoint = matches[0] if matches else None
    if endpoint is None:
        raise BoundaryRefused(f"model endpoint {endpoint_id!r} is not declared")
    if endpoint.get("endpoint") != "https://api.typesafe.ai/v1/systemone":
        raise BoundaryRefused("unapproved System One endpoint")
    for field in ("vendor", "terms_version", "approved_by", "approved_at"):
        if not isinstance(endpoint.get(field), str) or not endpoint[field].strip():
            raise BoundaryRefused(f"endpoint ticket is missing {field}")
    try:
        approved_at = datetime.fromisoformat(endpoint["approved_at"].replace("Z", "+00:00"))
        if approved_at.utcoffset() is None:
            raise ValueError("timezone missing")
    except ValueError:
        raise BoundaryRefused("endpoint approval timestamp is invalid") from None
    if endpoint.get("boundary") != "vendor-cloud":
        raise BoundaryRefused("System One requires a vendor-cloud boundary")
    if endpoint.get("training_on_customer_data") not in {"unknown", "yes", "no"}:
        raise BoundaryRefused("endpoint ticket is missing training status")
    for control in ("zdr", "baa"):
        value = endpoint.get(control)
        if not isinstance(value, dict) or value.get("status") not in {"unknown", "not-in-force", "in-force"} or "ref" not in value:
            raise BoundaryRefused(f"endpoint ticket is missing {control} status")
        if value["status"] == "in-force" and not value.get("ref"):
            raise BoundaryRefused(f"{control} in force requires a contract reference")
    if "transfer_mechanism" not in endpoint:
        raise BoundaryRefused("endpoint ticket is missing transfer status")
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
