"""Deterministic rules: what a match and a transaction context legally imply.

This is the second half of the deterministic layer. The matcher answers "is
this the listed party"; the rules engine answers "and what does that mean for
this shipment". Both run before any model is invoked, and both are pure
functions, so the legal skeleton of a screening decision never depends on a
sampled token.

The rules deliberately stop short of giving an answer where the answer is
genuinely entry-specific -- an Entity List hit produces "licence required per
the scope of the entry, read it", not a verdict. Manufacturing false
precision is worse than surfacing the question.

Nothing here is legal advice. Every country rule cites the policy file's
`as_of` date so a stale policy shows up in the output rather than hiding.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .models import Candidate, ScreeningResult, SubjectParty
from .names import fold

POLICY_PATH = Path(__file__).parent / "policy" / "destinations.json"

Severity = str  # "prohibitive" | "license" | "diligence" | "informational"


@dataclass
class RuleFlag:
    rule_id: str
    severity: Severity
    title: str
    basis: str
    detail: str
    action_required: str
    policy_as_of: str = ""
    unverified_policy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Policy:
    as_of: str
    verified_by: str
    verified_on: str
    countries: dict[str, dict]
    regions: list[dict]
    transshipment: set[str]
    aliases: dict[str, str]
    tiers: dict[str, str] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return bool(self.verified_by and self.verified_on)

    def resolve_country(self, raw: str) -> str:
        """Free-text country -> ISO2, or "" when unresolvable."""
        s = fold(raw)
        if not s:
            return ""
        if len(s) == 2 and s.upper() in self.countries:
            return s.upper()
        if s in self.aliases:
            return self.aliases[s]
        if len(s) == 2:
            return s.upper()
        for alias, iso in self.aliases.items():
            if s == alias:
                return iso
        return ""


def load_policy(path: Path | None = None) -> Policy:
    raw = json.loads(Path(path or POLICY_PATH).read_text(encoding="utf-8"))
    return Policy(
        as_of=raw.get("as_of", ""),
        verified_by=raw.get("verified_by", ""),
        verified_on=raw.get("verified_on", ""),
        countries={c["iso2"]: c for c in raw.get("countries", [])},
        regions=raw.get("regions", []),
        transshipment=set(raw.get("transshipment_watch", {}).get("countries", [])),
        aliases={fold(k): v for k, v in raw.get("aliases", {}).items() if not k.startswith("$")},
        tiers=raw.get("tiers", {}),
    )


# --------------------------------------------------------------------------
# Keyword triggers for end-use screening
# --------------------------------------------------------------------------
# Crude on purpose. These exist to force the question into the LLM analysis
# stage and into the human's field of view -- they are not a classification.

END_USE_TRIGGERS: dict[str, tuple[str, ...]] = {
    "nuclear": ("nuclear", "reactor", "enrich", "centrifuge", "uranium", "plutonium",
                "heavy water", "isotope separation", "yellowcake"),
    "missile": ("missile", "rocket motor", "ballistic", "guidance set", "reentry",
                "launch vehicle", "uav", "unmanned aerial", "drone"),
    "chem_bio": ("chemical weapon", "biological agent", "toxin", "precursor chemical",
                 "nerve agent", "select agent", "fermenter", "aerosol dispersal"),
    "military": ("military", "defense", "defence", "armed forces", "army", "navy",
                 "air force", "weapon", "munition", "warhead", "armor", "armour"),
    "surveillance": ("surveillance", "interception", "lawful intercept", "facial recognition",
                     "signals intelligence", "sigint", "deep packet"),
    "semiconductor": ("lithography", "wafer fab", "etch tool", "deposition tool",
                      "semiconductor manufacturing equipment", "advanced node", "euv"),
}

# BIS "Know Your Customer" red flags reducible to text signals.
# Supplement No. 3 to 15 CFR Part 732.
KYC_TEXT_FLAGS: dict[str, tuple[str, ...]] = {
    "reluctant_end_use": ("declined to provide", "will not disclose", "prefers not to say",
                          "end use unknown", "unknown end user", "not disclosed"),
    "capability_mismatch": ("no prior experience", "unrelated industry", "first order",
                            "capability mismatch"),
    "unusual_shipping": ("hold for pickup", "freight forwarder is final", "reship",
                         "transship", "onward shipment", "address is a freight"),
    "unusual_payment": ("cash in advance", "wire from third country", "third party payer",
                        "unusual payment", "cryptocurrency"),
    "declined_service": ("declines installation", "no training required", "refused warranty",
                         "no maintenance contract"),
}


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------

def _policy_note(p: Policy) -> tuple[str, bool]:
    if p.verified:
        return f"policy verified {p.verified_on} by {p.verified_by}", False
    return (
        f"policy file as_of {p.as_of} has NOT been verified by an operator -- "
        "confirm against the current CFR before relying on this flag"
    ), True


def destination_rules(subject: SubjectParty, p: Policy) -> list[RuleFlag]:
    out: list[RuleFlag] = []
    note, unverified = _policy_note(p)
    raw_dest = subject.destination_country or subject.country
    iso = p.resolve_country(raw_dest)
    addr = fold(f"{subject.address} {raw_dest}")

    # Regional embargoes are matched on address text, because "Ukraine" as a
    # country code tells you nothing about whether the address is in Crimea.
    for region in p.regions:
        if any(term in addr for term in region.get("match_terms", [])):
            out.append(RuleFlag(
                rule_id="DEST.REGION",
                severity="prohibitive",
                title=f"Address falls in an embargoed region: {region['name']}",
                basis=region.get("basis", ""),
                detail=(
                    f"Address text matched an embargoed-region term. Region "
                    f"embargoes apply regardless of the country field."
                ),
                action_required=(
                    "Stop. Do not proceed without a specific OFAC authorization. "
                    "Confirm the physical location before concluding."
                ),
                policy_as_of=p.as_of, unverified_policy=unverified,
            ))

    if not iso:
        if raw_dest:
            out.append(RuleFlag(
                rule_id="DEST.UNRESOLVED",
                severity="diligence",
                title=f"Destination country '{raw_dest}' could not be resolved",
                basis="internal data quality",
                detail="Country screening did not run for this party.",
                action_required="Normalize the destination to an ISO 3166-1 alpha-2 code and re-screen.",
                policy_as_of=p.as_of, unverified_policy=unverified,
            ))
        else:
            out.append(RuleFlag(
                rule_id="DEST.MISSING",
                severity="diligence",
                title="No destination country supplied",
                basis="15 CFR 732.3 (steps for using the EAR)",
                detail="Destination is one of the five facts an EAR analysis requires.",
                action_required="Supply the ultimate destination and re-screen.",
                policy_as_of=p.as_of, unverified_policy=unverified,
            ))
        return out

    entry = p.countries.get(iso)
    if entry:
        tiers = entry.get("tiers", [])
        if "comprehensive" in tiers:
            out.append(RuleFlag(
                rule_id="DEST.COMPREHENSIVE",
                severity="prohibitive",
                title=f"{entry['name']} is subject to comprehensive restrictions",
                basis=entry.get("basis", ""),
                detail=f"{note}. {p.tiers.get('comprehensive', '')}",
                action_required=(
                    "Treat as licence-required/prohibited until an authorization or "
                    "exemption is identified in writing. Do not ship on the strength "
                    "of a clear name screen alone."
                ),
                policy_as_of=p.as_of, unverified_policy=unverified,
            ))
        if "extensive" in tiers:
            out.append(RuleFlag(
                rule_id="DEST.EXTENSIVE",
                severity="license",
                title=f"{entry['name']} carries extensive item-specific controls",
                basis=entry.get("basis", ""),
                detail=f"{note}. {p.tiers.get('extensive', '')}",
                action_required=(
                    "Perform a full licence analysis against the item's ECCN and the "
                    "applicable country-specific rules before proceeding."
                ),
                policy_as_of=p.as_of, unverified_policy=unverified,
            ))
        if "itar_proscribed" in tiers:
            out.append(RuleFlag(
                rule_id="DEST.ITAR126",
                severity="prohibitive",
                title=f"{entry['name']} is a 22 CFR 126.1 proscribed destination",
                basis=entry.get("basis", "22 CFR 126.1"),
                detail=(
                    f"{note}. A United States policy of denial applies to defense "
                    "articles and defense services for this destination."
                ),
                action_required=(
                    "Confirm whether the item is ITAR-controlled. If it is on the "
                    "USML, this is effectively a stop."
                ),
                policy_as_of=p.as_of, unverified_policy=unverified,
            ))
        if "targeted" in tiers and not {"comprehensive", "extensive"} & set(tiers):
            out.append(RuleFlag(
                rule_id="DEST.TARGETED",
                severity="diligence",
                title=f"{entry['name']} has targeted sanctions programs",
                basis=entry.get("basis", ""),
                detail=f"{note}. {p.tiers.get('targeted', '')}",
                action_required="Rely on party screening and confirm no program-specific prohibition applies.",
                policy_as_of=p.as_of, unverified_policy=unverified,
            ))

    if iso in p.transshipment:
        out.append(RuleFlag(
            rule_id="DEST.TRANSSHIP",
            severity="diligence",
            title=f"{iso} is a recognized diversion/transshipment watch jurisdiction",
            basis="BIS/OFAC/FinCEN joint export-control-evasion alerts",
            detail=(
                f"{note}. Presence on this list is not a prohibition; it raises the "
                "required standard of end-user diligence."
            ),
            action_required=(
                "Obtain and retain an end-user statement identifying the ultimate "
                "consignee and end use. Document why diversion risk is acceptable."
            ),
            policy_as_of=p.as_of, unverified_policy=unverified,
        ))
    return out


def _order_active(cand: Candidate, as_of: date) -> tuple[bool, str]:
    """Is a dated denial order in force on the transaction date?"""
    lp = cand.listed_party or {}
    def _d(v: str) -> date | None:
        v = (v or "").strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%y", "%Y/%m/%d"):
            try:
                return datetime.strptime(v, fmt).date()
            except ValueError:
                continue
        return None
    start, end = _d(lp.get("effective_date", "")), _d(lp.get("expiration_date", ""))
    if end and end < as_of:
        return False, f"order expired {end.isoformat()}"
    if start and start > as_of:
        return False, f"order not effective until {start.isoformat()}"
    if not start and not end:
        return True, "no date range published; assumed in force"
    return True, "in force on the transaction date"


def list_hit_rules(cands: list[Candidate], as_of: date) -> list[RuleFlag]:
    """Translate deterministic matches into legal consequence."""
    out: list[RuleFlag] = []
    for c in cands:
        if c.band == "NONE":
            continue
        src = c.listed_source
        strength = "confirmed-strength name match" if c.band == "EXACT" else f"{c.band.lower()} name match"

        if src == "UNKNOWN":
            out.append(RuleFlag(
                rule_id="LIST.UNKNOWN_SOURCE",
                severity="diligence",
                title=f"Match on a row whose source list could not be identified: {c.listed_name}",
                basis="internal data quality",
                detail="Legal effect cannot be determined from the loaded data.",
                action_required="Read the primary publication for this row before clearing or blocking.",
            ))
            continue

        if src in ("DPL",):
            active, why = _order_active(c, as_of)
            out.append(RuleFlag(
                rule_id="LIST.DPL",
                severity="prohibitive" if active else "informational",
                title=f"Denied Persons List {strength}: {c.listed_name}",
                basis="15 CFR Part 764; the applicable denial order",
                detail=f"{c.legal_effect} Order status: {why}.",
                action_required=(
                    "Do not participate in any transaction subject to the EAR "
                    "involving this party while the order is in force."
                    if active else
                    "Confirm the order dates against the transaction date; this "
                    "flag is informational if the order is not in force."
                ),
            ))
        elif src == "SDN":
            out.append(RuleFlag(
                rule_id="LIST.SDN",
                severity="prohibitive",
                title=f"OFAC SDN {strength}: {c.listed_name}",
                basis="31 CFR Chapter V",
                detail=c.legal_effect,
                action_required=(
                    "If the match is confirmed, block or reject the transaction and "
                    "file the required OFAC report within 10 business days."
                ),
            ))
            if (c.listed_party or {}).get("party_type") in ("entity", "unknown"):
                out.append(RuleFlag(
                    rule_id="LIST.SDN50",
                    severity="diligence",
                    title="OFAC 50 Percent Rule analysis required",
                    basis="OFAC Revised Guidance on Entities Owned by Blocked Persons",
                    detail=(
                        "Entities owned 50 percent or more, directly or indirectly, in "
                        "the aggregate by one or more blocked persons are themselves "
                        "blocked and do NOT appear on the SDN List. Name screening "
                        "cannot detect them."
                    ),
                    action_required=(
                        "Obtain beneficial-ownership information for the counterparty "
                        "and any parent. Document the ownership conclusion."
                    ),
                ))
        elif src == "NONSDN":
            programs = ", ".join((c.listed_party or {}).get("programs", [])) or "unspecified"
            out.append(RuleFlag(
                rule_id="LIST.NONSDN",
                severity="license",
                title=f"OFAC Non-SDN {strength}: {c.listed_name}",
                basis="31 CFR Chapter V; program directives",
                detail=(
                    f"{c.legal_effect} Program tag(s): {programs}. This is generally "
                    "NOT a blocking designation."
                ),
                action_required=(
                    "Read the specific directive for the program tag. Do not apply "
                    "blocking treatment by default, and do not clear the party either."
                ),
            ))
        elif src == "EL":
            out.append(RuleFlag(
                rule_id="LIST.ENTITY",
                severity="license",
                title=f"BIS Entity List {strength}: {c.listed_name}",
                basis="15 CFR Part 744, Supplement No. 4",
                detail=(
                    f"{c.legal_effect} Entry remarks: "
                    f"{(c.listed_party or {}).get('remarks', '') or 'none captured'}"
                ),
                action_required=(
                    "Read the actual Entity List entry. The licence requirement is "
                    "scoped to the items named there, and footnote designations may "
                    "trigger a Foreign Direct Product Rule."
                ),
            ))
        elif src == "UVL":
            out.append(RuleFlag(
                rule_id="LIST.UVL",
                severity="diligence",
                title=f"BIS Unverified List {strength}: {c.listed_name}",
                basis="15 CFR 744.15",
                detail=c.legal_effect,
                action_required=(
                    "Obtain a UVL statement from the party before an NLR shipment. "
                    "No licence exceptions are available. Do not auto-block."
                ),
            ))
        elif src == "MEU":
            out.append(RuleFlag(
                rule_id="LIST.MEU",
                severity="license",
                title=f"BIS Military End User List {strength}: {c.listed_name}",
                basis="15 CFR 744.21 and Supplement No. 7",
                detail=c.legal_effect,
                action_required=(
                    "Licence required for Supplement No. 2 items, presumption of "
                    "denial. Note that 744.21 also applies to unlisted military end "
                    "users -- the list is not the whole obligation."
                ),
            ))
        elif src == "DTC":
            out.append(RuleFlag(
                rule_id="LIST.DDTC",
                severity="prohibitive",
                title=f"ITAR Debarred {strength}: {c.listed_name}",
                basis="22 CFR 127.7",
                detail=c.legal_effect,
                action_required=(
                    "Exclude from any ITAR-controlled activity. Confirm the listing "
                    "on the DDTC site before acting."
                ),
            ))
        elif src == "ISN":
            out.append(RuleFlag(
                rule_id="LIST.ISN",
                severity="license",
                title=f"Nonproliferation sanctions {strength}: {c.listed_name}",
                basis="INKSNA / CBW Act / related determinations",
                detail=c.legal_effect,
                action_required="Read the Federal Register determination for the applicable measures.",
            ))
    return out


def end_use_rules(subject: SubjectParty) -> list[RuleFlag]:
    out: list[RuleFlag] = []
    text = fold(f"{subject.item_description} {subject.end_use} {subject.role}")
    if not text.strip():
        out.append(RuleFlag(
            rule_id="USE.MISSING",
            severity="diligence",
            title="No item description or end use supplied",
            basis="15 CFR Part 732, Supplement No. 3 (Know Your Customer guidance)",
            detail="End-use and end-user screening did not run for this party.",
            action_required="Supply the item and stated end use, then re-screen.",
        ))
        return out

    for category, terms in END_USE_TRIGGERS.items():
        hit = [t for t in terms if t in text]
        if hit:
            out.append(RuleFlag(
                rule_id=f"USE.{category.upper()}",
                severity="diligence",
                title=f"End-use text contains {category.replace('_', '/')} indicators",
                basis="15 CFR 744.2-744.6 (proliferation end-use controls); 744.21",
                detail=f"Matched terms: {', '.join(sorted(hit))}. Keyword signal only, not a classification.",
                action_required=(
                    "Perform the applicable end-use analysis. A keyword hit is a "
                    "prompt to look, not a finding."
                ),
            ))

    for flag, terms in KYC_TEXT_FLAGS.items():
        hit = [t for t in terms if t in text]
        if hit:
            out.append(RuleFlag(
                rule_id=f"KYC.{flag.upper()}",
                severity="diligence",
                title=f"Know-Your-Customer red flag: {flag.replace('_', ' ')}",
                basis="15 CFR Part 732, Supplement No. 3",
                detail=f"Matched: {', '.join(sorted(hit))}.",
                action_required=(
                    "Inquire, and document the inquiry and its resolution. BIS "
                    "guidance requires red flags to be resolved, not ignored."
                ),
            ))

    role = fold(subject.role)
    if any(r in role for r in ("forwarder", "broker", "agent", "intermediary", "trading")):
        out.append(RuleFlag(
            rule_id="KYC.INTERMEDIARY",
            severity="diligence",
            title="Counterparty is an intermediary, not an end user",
            basis="15 CFR Part 732, Supplement No. 3; 15 CFR 758.3 (routed transactions)",
            detail="Screening an intermediary does not discharge the duty to know the ultimate end user.",
            action_required="Identify and separately screen the ultimate consignee and end user.",
        ))
    return out


def classification_rules(subject: SubjectParty) -> list[RuleFlag]:
    out: list[RuleFlag] = []
    eccn = (subject.eccn or "").strip().upper()
    if not eccn:
        out.append(RuleFlag(
            rule_id="CLASS.MISSING",
            severity="diligence",
            title="No ECCN or EAR99 determination recorded",
            basis="15 CFR 732.3(b); Part 774 (Commerce Control List)",
            detail=(
                "Party screening alone does not establish whether a licence is "
                "required. Classification is a separate, mandatory step."
            ),
            action_required="Classify the item (self-classification, CCATS, or counsel) and record the basis.",
        ))
    elif eccn == "EAR99":
        out.append(RuleFlag(
            rule_id="CLASS.EAR99",
            severity="informational",
            title="Item recorded as EAR99",
            basis="15 CFR 734.3(c)",
            detail=(
                "EAR99 items still require a licence for embargoed destinations, "
                "prohibited end users, and prohibited end uses."
            ),
            action_required="Confirm no destination, end-user or end-use control applies.",
        ))
    elif not re.fullmatch(r"\d[A-E]\d{3}([.]?[a-z0-9.]*)?", eccn, re.IGNORECASE):
        out.append(RuleFlag(
            rule_id="CLASS.MALFORMED",
            severity="diligence",
            title=f"ECCN '{subject.eccn}' does not match the CCL format",
            basis="15 CFR Part 774",
            detail="Expected a pattern like 3A001 or 5A002.a.1.",
            action_required="Correct the classification before relying on it.",
        ))
    return out


def evaluate(
    subject: SubjectParty,
    candidates: list[Candidate],
    policy: Policy | None = None,
    as_of: date | None = None,
) -> list[RuleFlag]:
    p = policy or load_policy()
    d = as_of or date.today()
    return [
        *list_hit_rules(candidates, d),
        *destination_rules(subject, p),
        *end_use_rules(subject),
        *classification_rules(subject),
    ]


SEVERITY_RANK = {"prohibitive": 3, "license": 2, "diligence": 1, "informational": 0}


def provisional_disposition(result: ScreeningResult) -> tuple[str, str]:
    """Deterministic disposition before any LLM sees the case.

    This is the floor. The LLM adjudication stage may raise severity but may
    never lower it below what this function returns -- see adjudicate.py.
    """
    band = result.top_band()
    flags = [RuleFlag(**f) if isinstance(f, dict) else f for f in result.rule_flags]
    worst = max((SEVERITY_RANK.get(f.severity, 0) for f in flags), default=0)

    if band == "EXACT":
        return "CONFIRMED_HIT", (
            "Exact normalized name match against a restricted party list. "
            "Requires human confirmation before any disposition other than hold."
        )
    if band == "STRONG":
        return "REVIEW", "Strong name match requires adjudication and human sign-off."
    if band == "WEAK":
        return "REVIEW", "Weak name match requires adjudication."
    if worst >= 3:
        return "REVIEW", "No name match, but a prohibitive transaction rule fired."
    if worst >= 1:
        return "REVIEW", "No name match, but diligence obligations are outstanding."
    return "CLEAR", "No candidate above the review floor and no outstanding rule flags."
