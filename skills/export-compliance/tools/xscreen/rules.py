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
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import Candidate, ScreeningResult, SubjectParty, stable_digest
from .names import fold
from .sources import legal_effect_for

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


# ISO 3166 "official" renderings and their ERP echoes put the generic part
# after a comma or in parentheses: "Iran, Islamic Republic of", "IRAN
# (ISLAMIC REPUBLIC OF)", "Congo, Democratic Republic of the". The alias
# table cannot enumerate every such spelling, and it does not have to: the
# fragment after the separator always ends in "of"/"of the", so rotating it
# to the front recovers the natural-order name the table does carry.
_ROTATE_RE = re.compile(r"^\s*([^,(]+?)\s*[,(]\s*([^)]+?)\s*\)?\s*$")


def _country_keys(raw: str) -> list[str]:
    """Folded alias-lookup keys for a free-text country, most literal first."""
    keys = [fold(raw)]
    m = _ROTATE_RE.match(raw or "")
    if m and fold(m.group(2)).endswith((" of", " of the")):
        keys.append(fold(f"{m.group(2)} {m.group(1)}"))
    # A leading article is decoration: "The Bahamas", "the Netherlands".
    for k in list(keys):
        if k.startswith("the "):
            keys.append(k[4:])
    return keys


@dataclass
class Policy:
    as_of: str
    verified_by: str
    verified_on: str
    countries: dict[str, dict]
    regions: list[dict]
    transshipment: set[str]
    aliases: dict[str, str]
    known_iso2: set[str] = field(default_factory=set)
    tiers: dict[str, str] = field(default_factory=dict)
    iso3: dict[str, str] = field(default_factory=dict)
    digest: str = ""

    @property
    def verified(self) -> bool:
        return bool(self.verified_by and self.verified_on)

    def resolve_country(self, raw: str) -> str:
        """Free-text country -> ISO2, or "" when unresolvable.

        A two-letter string is accepted only if it is a *known* ISO 3166-1
        alpha-2 code. Accepting any two characters was a false-clear hole: an
        unrecognized code like "KH" passed straight through, matched no policy
        entry, produced no destination flag at all, and the case reached CLEAR
        with exit code 0 -- while the schema told operators that "an
        unresolvable value raises DEST.UNRESOLVED rather than being ignored."
        Now it does.

        Resolution order: the alias table (plain names, ISO long forms in
        either the natural or the "X, Y of" / "X (Y of)" order, colloquial
        renderings), then a known alpha-2 code, then an alpha-3 code. The
        ISO-official forms matter because that is what ERP master data
        emits: "Iran, Islamic Republic of" used to fall out as
        DEST.UNRESOLVED -- a diligence flag -- on a comprehensively
        embargoed destination.
        """
        s = fold(raw)
        if not s:
            return ""
        for key in _country_keys(raw):
            if key in self.aliases:
                return self.aliases[key]
        if len(s) == 2 and s.upper() in self.known_iso2:
            return s.upper()
        if len(s) == 3 and s.upper() in self.iso3:
            return self.iso3[s.upper()]
        return ""


def load_policy(path: Path | None = None) -> Policy:
    text = Path(path or POLICY_PATH).read_text(encoding="utf-8")
    raw = json.loads(text)
    countries = {c["iso2"]: c for c in raw.get("countries", [])}
    transshipment = set(raw.get("transshipment_watch", {}).get("countries", []))
    aliases = {fold(k): v for k, v in raw.get("aliases", {}).items() if not k.startswith("$")}
    # Plain names resolve too -- the canonical name table and the name on
    # each policy entry -- without displacing a hand-written alias.
    for iso, name in raw.get("names", {}).items():
        if not iso.startswith("$") and name:
            aliases.setdefault(fold(name), iso)
    for iso, entry in countries.items():
        if entry.get("name"):
            aliases.setdefault(fold(entry["name"]), iso)
    iso3 = {k.upper(): v for k, v in raw.get("iso3", {}).items() if not k.startswith("$")}
    # Anything named anywhere in the file is a known code, plus the published
    # ISO 3166-1 alpha-2 list. Codes outside this set are typos or made up,
    # and must not resolve.
    known = (set(raw.get("known_iso2", [])) | set(countries) | transshipment
             | set(aliases.values()) | set(iso3.values()))
    return Policy(
        as_of=raw.get("as_of", ""),
        verified_by=raw.get("verified_by", ""),
        verified_on=raw.get("verified_on", ""),
        countries=countries,
        regions=raw.get("regions", []),
        transshipment=transshipment,
        aliases=aliases,
        known_iso2=known,
        tiers=raw.get("tiers", {}),
        iso3=iso3,
        # Hash the parsed content, not the file bytes, so reformatting is
        # not mistaken for a policy change while a value edit always is.
        digest=stable_digest({k: v for k, v in raw.items() if not k.startswith("$")}),
    )


@lru_cache(maxsize=1)
def default_policy() -> Policy:
    """The shipped policy file, parsed once per process.

    For callers that need country resolution but hold no policy of their
    own -- the matcher's geography signal. Re-reading and re-hashing the
    file per candidate would put a disk read inside the scoring loop.
    """
    return load_policy()


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

    # Absence of a country entry means "no restriction recorded in this file",
    # which is only trustworthy if somebody checked the file. While it is
    # unattested, say so on the destinations where saying nothing would
    # otherwise read as a clean bill of health. Attesting the file removes
    # this flag, which is the point -- the unverified state should cost
    # something rather than sit in a footnote.
    if entry is None and iso not in p.transshipment and unverified:
        out.append(RuleFlag(
            rule_id="DEST.NO_POLICY_ENTRY",
            severity="diligence",
            title=f"No country restriction recorded for {iso}, and the policy file is unattested",
            basis="15 CFR Part 740 Supp. 1; Part 746; 22 CFR 126.1",
            detail=(
                f"{note}. The shipped policy file lists restricted destinations "
                "only; a country's absence from it is not evidence that no "
                "restriction applies."
            ),
            action_required=(
                f"Confirm {iso} against the current Country Groups, Part 746 and "
                "22 CFR 126.1, then attest the policy file with `xscreen policy "
                "verify --by \"<name>\"` to clear this flag."
            ),
            policy_as_of=p.as_of, unverified_policy=True,
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


def _fse_tagged(cand: Candidate) -> bool:
    """OFAC tags FSE rows FSE-IR / FSE-SY inside its consolidated Non-SDN file."""
    programs = (cand.listed_party or {}).get("programs", []) or []
    return any(str(p).strip().upper().startswith("FSE") for p in programs)


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
                basis="31 CFR Chapter V; 31 CFR 501.603, 501.604",
                detail=c.legal_effect,
                action_required=(
                    "If the match is confirmed, determine whether the transaction "
                    "must be BLOCKED or REJECTED -- they are different legal acts "
                    "with different reports (blocked property: 31 CFR 501.603; "
                    "rejected transaction: 501.604), both generally due within 10 "
                    "business days. Returning property that must be blocked is "
                    "itself a prohibited transfer of blocked property. Do not "
                    "treat the two as interchangeable."
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
        elif src == "FSE" or (src == "NONSDN" and _fse_tagged(c)):
            # Foreign Sanctions Evaders used to fall through to the Non-SDN
            # rule: licence severity, "generally NOT a blocking designation".
            # Literally true -- an FSE listing does not block property -- and
            # dangerously misleading, because EO 13608 prohibits U.S. persons
            # from ALL transactions or dealings with the listed person. For a
            # shipment decision that is the prohibitive outcome, not the
            # "read the directive" one. The CSL carries FSE as its own source
            # label; OFAC's consolidated Non-SDN file carries it as a program
            # tag on a NONSDN row, so both routes land here.
            programs = ", ".join((c.listed_party or {}).get("programs", [])) or "unspecified"
            out.append(RuleFlag(
                rule_id="LIST.FSE",
                severity="prohibitive",
                title=f"OFAC Foreign Sanctions Evader {strength}: {c.listed_name}",
                basis=(
                    "Executive Order 13608 of May 1, 2012, sec. 1; OFAC Foreign "
                    "Sanctions Evaders List"
                ),
                detail=(
                    f"{legal_effect_for('FSE')} Program tag(s): {programs}. "
                    "Confirm against the current FSE List entry: the Syria leg "
                    "of the program was affected by the 2025 revocation of the "
                    "Syria sanctions program, and many FSE parties are also "
                    "SDNs, in which case the SDN blocking effect governs."
                ),
                action_required=(
                    "Do not proceed with any transaction or dealing involving "
                    "this party absent an OFAC license. FSE is a transaction "
                    "prohibition rather than a blocking action: property is not "
                    "frozen and the 31 CFR 501.603 blocked-property report does "
                    "not follow automatically, but a rejected transaction may be "
                    "reportable under 31 CFR 501.604 -- confirm with counsel. "
                    "Check for a parallel SDN entry before deciding which applies."
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
                basis="15 CFR 744.16; Supplement No. 4 to Part 744",
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

        # Ownership diligence on the Commerce side. OFAC's 50 Percent Rule is
        # well known and handled above for SDN hits; BIS adopted an analogous
        # Affiliates Rule extending Entity List, MEU and denial-order
        # restrictions to majority-owned affiliates. It was suspended for a
        # year in November 2025, and a suspension is not a repeal -- an
        # operator standing this up now may be inside the snap-back before
        # their first policy re-attestation.
        if src in ("EL", "MEU", "DPL"):
            out.append(RuleFlag(
                rule_id="LIST.BIS_AFFILIATE",
                severity="diligence",
                title="BIS affiliate-ownership analysis may be required",
                basis="15 CFR Part 744 (Affiliates Rule); one-year suspension published Nov 2025",
                detail=(
                    "The rule extends these restrictions to entities owned 50 percent "
                    "or more, directly or indirectly, in the aggregate, by listed "
                    "parties -- the Commerce analogue of OFAC's 50 Percent Rule. "
                    "Suspended as of this build. VERIFY THE CURRENT STATUS rather "
                    "than relying on this note; suspensions expire. Either way, "
                    "majority-owned affiliates appear on no list and cannot be found "
                    "by name screening."
                ),
                action_required=(
                    "Confirm whether the Affiliates Rule is in force on the "
                    "transaction date. If it is, obtain beneficial-ownership "
                    "information for the counterparty and its parents."
                ),
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
    elif not re.fullmatch(r"\d[A-E]\d{3}(\.[a-z0-9]+)*", eccn, re.IGNORECASE):
        # The suffix separator is required. The previous pattern made the dot
        # optional while still allowing trailing alphanumerics, so "3A0011"
        # and "3A001XYZ" passed as well-formed and the operator never got the
        # prompt to correct a mistyped classification.
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
        exact = [c for c in result.candidates if c.get("band") == "EXACT"]
        # OFAC marks weak aliases as low-quality identifiers. When every
        # EXACT candidate matched only through one, the automatic
        # CONFIRMED_HIT floor overstated the evidence -- and the guardrail
        # then forbade the adjudicator to disagree with it.
        if exact and all((c.get("signals") or {}).get("weak_alias") for c in exact):
            return "REVIEW", (
                "Exact name match, but only against weak aliases -- broad or "
                "generic akas the source list itself marks as low-quality "
                "identifiers. Requires adjudication and human review; a "
                "weak-alias hit alone does not auto-confirm."
            )
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
