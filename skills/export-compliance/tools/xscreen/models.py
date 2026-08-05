"""Canonical data model shared by every stage of the pipeline.

One `ListedParty` shape spans all sources so the matcher never has to know
which agency published a row. One `ScreeningResult` shape carries a party from
deterministic match through LLM adjudication and critic review, accumulating
evidence without ever discarding what an earlier stage concluded.

Everything is a plain dataclass with explicit `to_dict`/`from_dict` so results
serialize to JSON that a compliance officer can read five years from now
without this code.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

SCHEMA_VERSION = "1.0.0"

PartyType = Literal["individual", "entity", "vessel", "aircraft", "unknown"]

# Deterministic score bands. The matcher assigns these; nothing downstream may
# invent a new one.
MatchBand = Literal["EXACT", "STRONG", "WEAK", "NONE"]

# Final disposition of a screened party.
Disposition = Literal[
    "CLEAR",            # no candidate above the review floor
    "REVIEW",           # candidates exist, human/LLM adjudication needed
    "CONFIRMED_HIT",    # adjudicated as the listed party
    "BLOCKED",          # confirmed hit on a list that prohibits the dealing
    "ESCALATE",         # unresolved after critic loop -- human required
]


@dataclass
class ListedParty:
    """A single restricted party as published by a government list."""

    uid: str                       # stable id: "<source>:<native_id>"
    source: str                    # governing list code (SDN, EL, DPL, ...)
    native_id: str                 # id in the source file
    name: str                      # primary name as published
    party_type: PartyType = "unknown"
    aliases: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    programs: list[str] = field(default_factory=list)   # OFAC programs / EAR cites
    ids: list[str] = field(default_factory=list)        # passport, tax id, IMO...
    remarks: str = ""
    federal_register: str = ""
    effective_date: str = ""
    expiration_date: str = ""
    source_url: str = ""
    raw: dict[str, str] = field(default_factory=dict)

    def all_names(self) -> list[str]:
        """Primary name plus aliases, de-duplicated, order preserved."""
        seen: set[str] = set()
        out: list[str] = []
        for n in [self.name, *self.aliases]:
            n = (n or "").strip()
            if n and n.lower() not in seen:
                seen.add(n.lower())
                out.append(n)
        return out

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ListedParty":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class SubjectParty:
    """A party the operator wants screened -- a customer, vendor, or consignee."""

    ref: str                       # operator's own reference (row id, account no.)
    name: str
    party_type: PartyType = "unknown"
    country: str = ""
    address: str = ""
    role: str = ""                 # customer | end-user | consignee | freight-forwarder | ...
    aliases: list[str] = field(default_factory=list)
    # Transaction context -- drives the rules engine, not the name matcher.
    destination_country: str = ""
    eccn: str = ""
    item_description: str = ""
    end_use: str = ""
    raw: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SubjectParty":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class Candidate:
    """A deterministic match between a subject and a listed party.

    `score` and `band` come from `match.py` and are reproducible from the
    inputs alone. `signals` records *why*, so a reviewer can audit the score
    without rerunning the matcher.
    """

    listed_uid: str
    listed_name: str            # the specific name/alias that matched
    listed_source: str
    score: float
    band: MatchBand
    signals: dict[str, Any] = field(default_factory=dict)
    legal_effect: str = ""
    listed_party: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Candidate":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class Adjudication:
    """LLM judgement on one candidate. Advisory only -- see adjudicate.py."""

    listed_uid: str
    verdict: Literal["SAME_PARTY", "DIFFERENT_PARTY", "UNCERTAIN"]
    confidence: float
    rationale: str
    discriminating_evidence: list[str] = field(default_factory=list)
    model: str = ""
    # Set when a guardrail refused to let the LLM verdict stand.
    guardrail_override: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Adjudication":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class CriticFinding:
    """One objection raised by the critic against an adjudication."""

    listed_uid: str
    severity: Literal["critical", "major", "minor"]
    category: str
    finding: str
    suggested_action: str = ""


@dataclass
class ScreeningResult:
    """Everything known about one screened subject, at every stage."""

    subject: dict[str, Any]
    candidates: list[dict[str, Any]] = field(default_factory=list)
    rule_flags: list[dict[str, Any]] = field(default_factory=list)
    adjudications: list[dict[str, Any]] = field(default_factory=list)
    critic_findings: list[dict[str, Any]] = field(default_factory=list)
    disposition: Disposition = "CLEAR"
    disposition_reason: str = ""
    requires_human: bool = False
    # Provenance of the list data this result was computed against.
    list_manifest_digest: str = ""
    engine_version: str = SCHEMA_VERSION
    screened_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScreeningResult":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def top_band(self) -> MatchBand:
        order = {"EXACT": 3, "STRONG": 2, "WEAK": 1, "NONE": 0}
        best: MatchBand = "NONE"
        for c in self.candidates:
            if order.get(c.get("band", "NONE"), 0) > order[best]:
                best = c["band"]
        return best


def stable_digest(payload: Any) -> str:
    """SHA-256 over a canonical JSON rendering.

    Used for the list manifest digest and the audit chain. Sorting keys and
    forcing separators makes the digest reproducible across Python versions
    and machines, which is the whole point of putting it in an audit record.
    """
    import json

    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
