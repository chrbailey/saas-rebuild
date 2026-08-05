"""Registry of official U.S. government restricted-party sources.

Every entry records where the data comes from, how to parse it, and -- the part
that matters to a lawyer -- what a hit on that list actually *prohibits*. The
legal-effect strings here are deliberately terse and are not legal advice; they
exist so a screening result can never be rendered as a bare "HIT" with no
statement of consequence.

Design rule: the Consolidated Screening List (CSL) is the default *operational*
source because it is one clean file covering all agencies. It is NOT the legal
source of record. Anything that will be relied on for a licensing decision must
be confirmed against the primary list and the Federal Register notice. See
`references/legal-effect-matrix.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Agency = Literal["Commerce/BIS", "Treasury/OFAC", "State/DDTC", "State/ISN", "Multiple"]
Fmt = Literal["csv", "tsv", "txt-tab", "xml", "json"]


@dataclass(frozen=True)
class Source:
    """One downloadable government list."""

    code: str
    name: str
    agency: Agency
    urls: tuple[str, ...]
    fmt: Fmt
    parser: str
    legal_effect: str
    authority: str
    # True when the file is an aggregation of other lists rather than the
    # legally operative publication.
    aggregate: bool = False
    # Screening still requires a separate analysis this file cannot answer.
    caveats: tuple[str, ...] = field(default_factory=tuple)
    requires_key: bool = False


# --------------------------------------------------------------------------
# Primary aggregate
# --------------------------------------------------------------------------

CSL = Source(
    code="CSL",
    name="Consolidated Screening List",
    agency="Multiple",
    urls=(
        "https://data.trade.gov/downloadable_consolidated_screening_list/v1/consolidated.csv",
        "https://api.trade.gov/static/consolidated_screening_list/consolidated.csv",
    ),
    fmt="csv",
    parser="csl",
    legal_effect=(
        "Aggregation only. Legal effect is determined by the underlying list "
        "identified in the row's `source` field -- see that list's entry."
    ),
    authority="ITA/trade.gov aggregation of BIS, OFAC, State and other lists",
    aggregate=True,
    caveats=(
        "Not the legal source of record. Confirm any hit against the primary "
        "list and the governing Federal Register notice before acting.",
        "Does not resolve OFAC's 50 Percent Rule: entities owned 50%+ by "
        "blocked persons are themselves blocked but are NOT listed here.",
        "Publication lag between a Federal Register action and CSL refresh is "
        "possible. Record the CSL publish date on every screening result.",
        "Aggregation can drop or flatten fields present in the primary file "
        "(notably OFAC alternate-name types and Entity List license policy).",
    ),
)

# --------------------------------------------------------------------------
# Treasury / OFAC
# --------------------------------------------------------------------------

SDN = Source(
    code="SDN",
    name="Specially Designated Nationals and Blocked Persons List",
    agency="Treasury/OFAC",
    urls=(
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV",
        "https://www.treasury.gov/ofac/downloads/sdn.csv",
    ),
    fmt="csv",
    parser="ofac_sdn",
    legal_effect=(
        "Property and interests in property of the listed person that come "
        "within U.S. jurisdiction are BLOCKED. U.S. persons are generally "
        "prohibited from dealing with them. Strict liability; civil penalties "
        "apply without regard to knowledge."
    ),
    authority="31 CFR Chapter V; various IEEPA-based sanctions programs",
    caveats=(
        "The 50 Percent Rule applies: an unlisted entity owned 50% or more, "
        "directly or indirectly, in the aggregate, by one or more blocked "
        "persons is itself blocked. Ownership analysis is out of scope for "
        "name matching and must be performed separately.",
        "Program tags on the row determine which prohibitions apply; not all "
        "SDN entries carry the same restrictions.",
    ),
)

SDN_ALT = Source(
    code="SDN_ALT",
    name="SDN Alternate Names (AKA) file",
    agency="Treasury/OFAC",
    urls=(
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ALT.CSV",
        "https://www.treasury.gov/ofac/downloads/alt.csv",
    ),
    fmt="csv",
    parser="ofac_alt",
    legal_effect="Alternate spellings/AKAs of SDN entries. Same effect as SDN.",
    authority="31 CFR Chapter V",
    caveats=(
        "Screening the primary-name file alone materially reduces recall. "
        "Load ALT alongside SDN or accept a known false-negative rate.",
    ),
)

SDN_ADD = Source(
    code="SDN_ADD",
    name="SDN Addresses file",
    agency="Treasury/OFAC",
    urls=(
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ADD.CSV",
        "https://www.treasury.gov/ofac/downloads/add.csv",
    ),
    fmt="csv",
    parser="ofac_add",
    legal_effect="Addresses associated with SDN entries. Same effect as SDN.",
    authority="31 CFR Chapter V",
)

NONSDN = Source(
    code="NONSDN",
    name="Non-SDN Consolidated Sanctions List",
    agency="Treasury/OFAC",
    urls=(
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/CONS_PRIM.CSV",
        "https://www.treasury.gov/ofac/downloads/consolidated/cons_prim.csv",
    ),
    fmt="csv",
    parser="ofac_sdn",
    legal_effect=(
        "Program-specific and generally NARROWER than blocking. Covers SSI "
        "(debt/equity restrictions), FSE, CAPTA, NS-PLC, NS-MBS, NS-CMIC and "
        "others. A hit here is usually NOT a full prohibition on dealing -- "
        "read the program tag and the governing directive."
    ),
    authority="31 CFR Chapter V; program-specific directives",
    caveats=(
        "Treating a Non-SDN hit as a blocking hit is a common and expensive "
        "error in both directions: it over-blocks lawful business and it "
        "masks the specific restriction that does apply.",
    ),
)

# --------------------------------------------------------------------------
# Commerce / BIS
# --------------------------------------------------------------------------

DPL = Source(
    code="DPL",
    name="Denied Persons List",
    agency="Commerce/BIS",
    urls=(
        "https://www.bis.doc.gov/dpl/dpl.txt",
        "https://media.bis.gov/dpl/dpl.txt",
    ),
    fmt="txt-tab",
    parser="bis_dpl",
    legal_effect=(
        "Export privileges DENIED by order. Participation in any transaction "
        "subject to the EAR involving the denied person is prohibited for the "
        "term of the order. No license exception is available."
    ),
    authority="15 CFR Part 764, Supplement No. 2; denial orders",
    caveats=(
        "Denial orders have effective and expiration dates. A stale copy of "
        "this file can both miss new denials and over-flag expired ones -- "
        "always evaluate the order's date range against the transaction date.",
    ),
)

ENTITY = Source(
    code="EL",
    name="Entity List",
    agency="Commerce/BIS",
    urls=(
        "https://www.bis.doc.gov/index.php/documents/consolidated-entity-list/1053-entity-list/file",
    ),
    fmt="csv",
    parser="bis_entity",
    legal_effect=(
        "A LICENSE is required for the items and scope specified in the "
        "listing, with a stated license review policy (frequently a "
        "presumption or policy of denial). License exceptions are limited or "
        "unavailable as specified in the entry."
    ),
    authority="15 CFR Part 744, Supplement No. 4",
    caveats=(
        "The license requirement is entry-specific: it applies to the items "
        "named in that entry, not automatically to all items. Reading a hit "
        "as a blanket prohibition, or as a blanket permission for unnamed "
        "items, are both wrong. Read the actual entry.",
        "Footnote designations (e.g. footnote 1, 3, 4, 5) carry additional "
        "rules such as the Foreign Direct Product Rules. These do not survive "
        "aggregation into CSL reliably.",
    ),
)

UVL = Source(
    code="UVL",
    name="Unverified List",
    agency="Commerce/BIS",
    urls=(
        "https://www.bis.doc.gov/index.php/documents/consolidated-entity-list/1054-unverified-list/file",
    ),
    fmt="csv",
    parser="bis_entity",
    legal_effect=(
        "No license exceptions may be used for exports involving a UVL party, "
        "and the exporter must obtain a UVL statement from the party before "
        "proceeding with an otherwise no-license-required transaction. Not a "
        "prohibition on dealing."
    ),
    authority="15 CFR Part 744, Supplement No. 6; 15 CFR 744.15",
    caveats=(
        "A UVL hit is a red flag requiring documented due diligence, not an "
        "automatic stop. Auto-blocking UVL parties is over-compliance.",
    ),
)

MEU = Source(
    code="MEU",
    name="Military End User List",
    agency="Commerce/BIS",
    urls=(
        "https://www.bis.doc.gov/index.php/documents/consolidated-entity-list/2949-supplement-no-7-to-part-744-military-end-user-list/file",
    ),
    fmt="csv",
    parser="bis_entity",
    legal_effect=(
        "License required for export/reexport/transfer of items listed in "
        "Supplement No. 2 to Part 744 to the listed party, with a presumption "
        "of denial."
    ),
    authority="15 CFR Part 744, Supplement No. 7; 15 CFR 744.21",
    caveats=(
        "744.21 also imposes an end-user/end-use obligation independent of "
        "this list: a party NOT on the MEU List can still be a military end "
        "user. List screening does not discharge the 744.21 duty.",
    ),
)

# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

DDTC = Source(
    code="DTC",
    name="ITAR Debarred Parties (statutory and administrative)",
    agency="State/DDTC",
    urls=("https://www.pmddtc.state.gov/ddtc_public",),
    fmt="csv",
    parser="csl_subset",
    legal_effect=(
        "Prohibited from participating directly or indirectly in the export "
        "of defense articles or defense services subject to the ITAR."
    ),
    authority="22 CFR 127.7; Arms Export Control Act",
    caveats=(
        "DDTC publishes these as web/PDF listings rather than a stable bulk "
        "CSV. The CSL 'DTC' subset is the practical bulk route; confirm any "
        "hit on the DDTC site.",
    ),
)

ISN = Source(
    code="ISN",
    name="Nonproliferation Sanctions",
    agency="State/ISN",
    urls=("https://www.state.gov/key-topics-bureau-of-international-security-and-nonproliferation/",),
    fmt="csv",
    parser="csl_subset",
    legal_effect=(
        "Measures vary by the statute under which the party was sanctioned "
        "(e.g. INKSNA, CBW Act). Read the Federal Register determination."
    ),
    authority="Various nonproliferation statutes",
    caveats=("Effect is determination-specific; no single rule applies.",),
)


ALL_SOURCES: tuple[Source, ...] = (
    CSL, SDN, SDN_ALT, SDN_ADD, NONSDN, DPL, ENTITY, UVL, MEU, DDTC, ISN,
)

BY_CODE: dict[str, Source] = {s.code: s for s in ALL_SOURCES}

# The default refresh set: CSL for breadth, plus the OFAC primaries because
# CSL's flattening of alternate names is the single biggest recall risk.
DEFAULT_REFRESH: tuple[str, ...] = ("CSL", "SDN", "SDN_ALT", "NONSDN", "DPL")

# Maximum age, in days, before a screening run refuses to proceed without an
# explicit override. Government lists change weekly or faster.
MAX_LIST_AGE_DAYS = 7

# CSL `source` values mapped to the list code whose legal effect governs.
# Keys are lowercased and stripped of punctuation for robust lookup.
CSL_SOURCE_MAP: dict[str, str] = {
    "denied persons list (dpl) - bureau of industry and security": "DPL",
    "denied persons list": "DPL",
    "entity list (el) - bureau of industry and security": "EL",
    "entity list": "EL",
    "unverified list (uvl) - bureau of industry and security": "UVL",
    "unverified list": "UVL",
    "military end user (meu) list - bureau of industry and security": "MEU",
    "military end user list": "MEU",
    "specially designated nationals (sdn) - treasury department": "SDN",
    "specially designated nationals list (sdn) - treasury department": "SDN",
    "sdn": "SDN",
    "sectoral sanctions identifications list (ssi) - treasury department": "NONSDN",
    "non-sdn menu-based sanctions list (ns-mbs list)": "NONSDN",
    "non-sdn chinese military-industrial complex companies list (ns-cmic)": "NONSDN",
    "non-sdn palestinian legislative council list (ns-plc)": "NONSDN",
    "foreign sanctions evaders (fse) - treasury department": "NONSDN",
    "capta list": "NONSDN",
    "itar debarred (dtc) - state department": "DTC",
    "nonproliferation sanctions (isn) - state department": "ISN",
}


def resolve_csl_source(raw: str) -> str:
    """Map a CSL `source` label to the governing list code.

    Returns "UNKNOWN" rather than guessing when the label is unrecognized --
    an unrecognized source must surface as an explicit gap, never be silently
    absorbed into a neighbouring list's legal effect.
    """
    key = " ".join((raw or "").lower().split())
    if key in CSL_SOURCE_MAP:
        return CSL_SOURCE_MAP[key]
    for label, code in CSL_SOURCE_MAP.items():
        if label in key or key in label:
            return code
    return "UNKNOWN"


def legal_effect_for(code: str) -> str:
    src = BY_CODE.get(code)
    if src is None:
        return (
            "UNKNOWN LIST -- legal effect could not be determined from the "
            "source data. Escalate to counsel; do not clear or block on this "
            "row without reading the primary publication."
        )
    return src.legal_effect
