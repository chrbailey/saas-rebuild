"""Parsers: raw government files -> canonical `ListedParty` records.

Each government file has its own shape, and those shapes change without
notice. Two rules keep that from becoming a silent recall failure:

1. **Header mapping is by alias set, not by position** (except for the OFAC
   flat files, which are genuinely headerless and positionally defined).
2. **Columns we do not recognize are reported, not dropped.** Every parser
   returns an `unmapped` set that the fetch manifest records. A new column
   named `alt_names_2` appearing in a CSL refresh must show up as a warning,
   not vanish.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field

from .models import ListedParty, PartyType
from .names import fold
from .sources import resolve_csl_source

# OFAC uses this sentinel for empty fields in its flat files.
OFAC_NULL = "-0-"

MULTI_SPLIT = re.compile(r"\s*;\s*|\s*\|\s*")


@dataclass
class ParseOutcome:
    parties: list[ListedParty] = field(default_factory=list)
    unmapped_columns: list[str] = field(default_factory=list)
    row_count: int = 0
    skipped_rows: int = 0
    warnings: list[str] = field(default_factory=list)


def _safe_raw(row: dict) -> dict[str, str]:
    """Snapshot a DictReader row without trusting its shape.

    A row with MORE fields than the header lands its extras under the key
    `None` as a list (csv.DictReader's documented restkey default). Calling
    .strip() on that list raised AttributeError and aborted the whole refresh
    on a single stray delimiter in a government file -- the opposite of this
    module's rule that a shape change surfaces as a warning rather than
    vanishing. Government CSV exports do get an unescaped delimiter sometimes.
    """
    return {k: v for k, v in row.items()
            if k is not None and isinstance(v, str) and v.strip()}


def _ragged(row: dict) -> str:
    """Describe a row whose field count disagrees with the header."""
    extra = row.get(None)
    if isinstance(extra, list) and extra:
        return f"{len(extra)} field(s) beyond the header: {extra[:3]}"
    missing = [k for k, v in row.items() if v is None]
    if missing:
        return f"{len(missing)} field(s) short of the header: {missing[:3]}"
    return ""


def _clean(v: str | None) -> str:
    if v is None:
        return ""
    v = v.strip()
    return "" if v in (OFAC_NULL, "") else v


def _split_multi(v: str | None) -> list[str]:
    v = _clean(v)
    if not v:
        return []
    return [p.strip() for p in MULTI_SPLIT.split(v) if p.strip()]


def _party_type(raw: str) -> PartyType:
    r = (raw or "").strip().lower()
    if r.startswith("individual") or r == "person":
        return "individual"
    if r.startswith("vessel"):
        return "vessel"
    if r.startswith("aircraft"):
        return "aircraft"
    if r in ("entity", "company", "organization"):
        return "entity"
    return "unknown"


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


# Alias sets for header-based formats. First match wins.
CSL_FIELDS: dict[str, tuple[str, ...]] = {
    # entity_number ties a row back to its source list and survives CSL
    # re-aggregation; the CSL row id does not. Prefer it, fall back to the row
    # id, and only then to the ordinal.
    "native_id": ("entity_number", "entity_num"),
    "row_id": ("id", "_id"),
    "name": ("name", "entity_name"),
    "party_type": ("type", "entity_type", "sdn_type"),
    "aliases": ("alt_names", "alternate_names", "aka", "alt_name"),
    "addresses": ("addresses", "address", "street_address"),
    "countries": ("countries", "country", "nationalities", "citizenships"),
    "programs": ("programs", "program", "sanctions_programs"),
    "remarks": ("remarks", "notes", "comment"),
    "federal_register": ("federal_register_notice", "fr_citation", "federal_register"),
    "effective_date": ("start_date", "effective_date"),
    "expiration_date": ("end_date", "expiration_date"),
    "source": ("source", "source_list", "list"),
    "source_url": ("source_list_url", "source_information_url", "url"),
    "ids": ("ids", "identifications", "id_numbers"),
    "license_requirement": ("license_requirement",),
    "license_policy": ("license_policy",),
    # Identity discriminators. The adjudication playbook names date and place
    # of birth as among the few facts that genuinely distinguish two similarly
    # named individuals -- and they were being reported as unmapped columns
    # and dropped before the adjudicator ever saw them. Vessel identifiers are
    # the same argument for the vessel entries.
    "dates_of_birth": ("dates_of_birth", "date_of_birth", "dob"),
    "places_of_birth": ("places_of_birth", "place_of_birth", "pob"),
    "title": ("title",),
    "call_sign": ("call_sign",),
    "vessel_flag": ("vessel_flag",),
    "vessel_owner": ("vessel_owner",),
    "vessel_type": ("vessel_type",),
}

# Fields folded into `ListedParty.ids` as labelled discriminators, because
# that is the field the adjudicator is shown.
CSL_DISCRIMINATORS: tuple[tuple[str, str], ...] = (
    ("dates_of_birth", "DOB"),
    ("places_of_birth", "POB"),
    ("title", "title"),
    ("call_sign", "call sign"),
    ("vessel_flag", "vessel flag"),
    ("vessel_owner", "vessel owner"),
    ("vessel_type", "vessel type"),
)

BIS_ENTITY_FIELDS: dict[str, tuple[str, ...]] = {
    "name": ("entity_name", "name", "listed_name"),
    "countries": ("country", "countries"),
    "addresses": ("address", "addresses", "street_address"),
    "federal_register": ("federal_register_notice", "fr_citation"),
    "effective_date": ("effective_date", "date"),
    "license_requirement": ("license_requirement", "license_requirements"),
    "license_policy": ("license_review_policy", "license_policy"),
    "aliases": ("alias", "aliases", "aka", "alternate_name"),
    "native_id": ("id", "entity_number"),
}

BIS_DPL_FIELDS: dict[str, tuple[str, ...]] = {
    "name": ("name",),
    "addresses": ("street_address",),
    "city": ("city",),
    "state": ("state",),
    "countries": ("country",),
    "postal_code": ("postal_code",),
    "effective_date": ("effective_date",),
    "expiration_date": ("expiration_date",),
    "standard_order": ("standard_order",),
    "federal_register": ("fr_citation", "federal_register_notice"),
    "action": ("action",),
}


def _build_map(headers: list[str], spec: dict[str, tuple[str, ...]]) -> tuple[dict[str, str], list[str]]:
    """Return (canonical_field -> actual_header, unmapped_headers)."""
    norm = {_norm_header(h): h for h in headers}
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for canon, aliases in spec.items():
        for a in aliases:
            if a in norm:
                mapping[canon] = norm[a]
                used.add(norm[a])
                break
    unmapped = [h for h in headers if h not in used and _norm_header(h)]
    return mapping, unmapped


def _get(row: dict[str, str], mapping: dict[str, str], canon: str) -> str:
    h = mapping.get(canon)
    return _clean(row.get(h)) if h else ""


# --------------------------------------------------------------------------
# Consolidated Screening List
# --------------------------------------------------------------------------

def parse_csl(text: str, source_filter: str | None = None) -> ParseOutcome:
    """Parse the CSL CSV.

    `source_filter` restricts to one underlying list code (used for the DDTC
    and ISN subsets, which have no separate bulk file).
    """
    out = ParseOutcome()
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        out.warnings.append("CSL file had no header row; nothing parsed.")
        return out
    mapping, unmapped = _build_map(list(reader.fieldnames), CSL_FIELDS)
    out.unmapped_columns = unmapped
    if "name" not in mapping:
        out.warnings.append(
            "CSL header has no recognizable name column; refusing to parse "
            f"rather than guess. Headers seen: {reader.fieldnames}"
        )
        return out

    unknown_sources: set[str] = set()
    ragged = 0
    for i, row in enumerate(reader):
        out.row_count += 1
        if (desc := _ragged(row)):
            ragged += 1
            if ragged <= 3:
                out.warnings.append(f"CSL row {i + 2} is ragged -- {desc}")
        name = _get(row, mapping, "name")
        if not name:
            out.skipped_rows += 1
            continue
        raw_source = _get(row, mapping, "source")
        code = resolve_csl_source(raw_source)
        if code == "UNKNOWN" and raw_source:
            unknown_sources.add(raw_source)
        if source_filter and code != source_filter:
            continue
        native = _get(row, mapping, "native_id") or _get(row, mapping, "row_id") or f"row{i}"
        remarks_parts = [_get(row, mapping, "remarks")]
        for extra in ("license_requirement", "license_policy"):
            v = _get(row, mapping, extra)
            if v:
                remarks_parts.append(f"{extra.replace('_', ' ')}: {v}")
        out.parties.append(
            ListedParty(
                uid=f"{code}:{native}",
                source=code,
                native_id=native,
                name=name,
                party_type=_party_type(_get(row, mapping, "party_type")),
                aliases=_split_multi(_get(row, mapping, "aliases")),
                addresses=_split_multi(_get(row, mapping, "addresses")),
                countries=_split_multi(_get(row, mapping, "countries")),
                programs=_split_multi(_get(row, mapping, "programs")),
                ids=_split_multi(_get(row, mapping, "ids")) + [
                    f"{label}: {v}"
                    for field, label in CSL_DISCRIMINATORS
                    for v in _split_multi(_get(row, mapping, field))
                ],
                remarks=" | ".join(p for p in remarks_parts if p),
                federal_register=_get(row, mapping, "federal_register"),
                effective_date=_get(row, mapping, "effective_date"),
                expiration_date=_get(row, mapping, "expiration_date"),
                source_url=_get(row, mapping, "source_url"),
                raw=_safe_raw(row),
            )
        )
    if ragged > 3:
        out.warnings.append(
            f"{ragged} CSL rows in total had a field count disagreeing with the "
            "header. The file layout may have changed; verify the parser against "
            "the current publication before trusting this snapshot."
        )
    if unknown_sources:
        out.warnings.append(
            "CSL rows carried source labels this build does not recognize, so "
            "their legal effect is UNKNOWN and they will escalate rather than "
            f"resolve: {sorted(unknown_sources)}. Add them to CSL_SOURCE_MAP."
        )
    return out


def parse_csl_subset(text: str, subset: str) -> ParseOutcome:
    return parse_csl(text, source_filter=subset)


# --------------------------------------------------------------------------
# OFAC flat files (headerless, positionally defined)
# --------------------------------------------------------------------------

SDN_COLS = 12   # ent_num, name, type, program, title, call_sign, vess_type,
                # tonnage, grt, vess_flag, vess_owner, remarks
ALT_COLS = 5    # ent_num, alt_num, alt_type, alt_name, alt_remarks
ADD_COLS = 6    # ent_num, add_num, address, city_state_zip, country, remarks


# Aliases OFAC records only in the free-text remarks of the primary file
# ("a.k.a. FARQAD GENERAL TRADING." / "a.k.a. 'THE TEACHER'"). These never
# reach the ALT file, so without extraction they were never indexed and never
# screened. They are treated as weak: free-text extraction is lower-quality
# provenance than a structured ALT row, so an exact hit on one routes to
# review rather than auto-confirming.
_REMARKS_AKA = re.compile(
    r"(?:a\.k\.a\.|f\.k\.a\.|n\.k\.a\.)\s+"
    r"(?:['\"]([^'\"]{2,120})['\"]|([^;.]{2,120}))",
    re.IGNORECASE,
)


def _remarks_akas(remarks: str) -> list[str]:
    out: list[str] = []
    for quoted, bare in _REMARKS_AKA.findall(remarks or ""):
        name = (quoted or bare).strip()
        if name:
            out.append(name)
    return out


# Values OFAC uses in the SDN type column. Used as a content sanity check:
# the flat files are positionally defined, so a column *count* check cannot
# detect a same-width reorder. If the field that should hold the party type
# stops looking like a party type, the layout has moved under us.
SDN_TYPE_VOCAB = frozenset({
    "individual", "entity", "vessel", "aircraft", "-0-", "",
})


def parse_ofac_sdn(text: str, source_code: str = "SDN") -> ParseOutcome:
    """Parse SDN.CSV or CONS_PRIM.CSV (identical layout, different list)."""
    out = ParseOutcome()
    type_seen = 0
    type_recognized = 0
    ragged = 0
    for row in csv.reader(io.StringIO(text)):
        if not row or not any(c.strip() for c in row):
            continue
        out.row_count += 1
        if len(row) < 4:
            out.skipped_rows += 1
            out.warnings.append(f"Short OFAC row ({len(row)} cols): {row[:3]}")
            continue
        if len(row) != SDN_COLS:
            # Throttled like the CSL ragged path: a layout change is one fact
            # about the file, and one warning per row turned it into 12,000
            # lines that buried every other warning in the manifest.
            ragged += 1
            if ragged <= 3:
                out.warnings.append(
                    f"OFAC row {out.row_count} had {len(row)} columns, expected "
                    f"{SDN_COLS}. Layout may have changed -- verify the parser "
                    "against the current file specification."
                )
        ent, name, typ, program = (_clean(row[0]), _clean(row[1]), _clean(row[2]), _clean(row[3]))
        type_seen += 1
        if (row[2] or "").strip().lower() in SDN_TYPE_VOCAB:
            type_recognized += 1
        if not name:
            out.skipped_rows += 1
            continue
        remarks = _clean(row[11]) if len(row) > 11 else ""
        akas = _remarks_akas(remarks)
        out.parties.append(
            ListedParty(
                uid=f"{source_code}:{ent}",
                source=source_code,
                native_id=ent,
                name=name,
                party_type=_party_type(typ),
                aliases=list(akas),
                weak_aliases=list(akas),
                programs=[p.strip() for p in re.split(r"[;\]\[]+", program) if p.strip()],
                remarks=remarks,
                raw={"row": " | ".join(row)},
            )
        )
    if ragged > 3:
        out.warnings.append(
            f"{ragged} {source_code} rows in total had a column count other than "
            f"{SDN_COLS}. The file layout may have changed; verify the parser "
            "against the current file specification before trusting this snapshot."
        )
    # A column-count check cannot catch a same-width reorder, which is a real
    # historical failure mode for headerless government files. If the party-type
    # column stops looking like party types, say so loudly -- a silently
    # misaligned parse produces names built from the wrong field, and every
    # subsequent screen against that snapshot is worthless.
    if type_seen >= 5 and type_recognized / type_seen < 0.6:
        out.warnings.append(
            f"Only {type_recognized}/{type_seen} rows had a recognizable value in "
            f"the {source_code} party-type column. This file is positionally "
            "defined, so that is a symptom of a COLUMN REORDER, not of unusual "
            "data. Verify the parser against the current file specification "
            "before screening against this snapshot."
        )
    return out


def parse_ofac_alt(text: str, source_code: str = "SDN") -> dict[str, list[tuple[str, bool]]]:
    """Return ent_num -> [(alternate name, is_weak)], to merge into SDN records.

    OFAC denotes a weak alias -- a broad, generic or otherwise low-quality
    aka -- by wrapping the name in quotation marks in the published data.
    The earlier version read only the name column and threw the distinction
    away, so an exact hit on a weak aka carried the same automatic
    CONFIRMED_HIT floor as a hit on a primary name, with the adjudicator
    forbidden to dissent. Weak aliases are still screened (they are on the
    list for a reason); they are just labelled as the lower-quality evidence
    they are.
    """
    out: dict[str, list[tuple[str, bool]]] = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 4:
            continue
        ent, alt_name = _clean(row[0]), _clean(row[3])
        if not (ent and alt_name):
            continue
        weak = len(alt_name) >= 3 and alt_name[0] in "\"'" and alt_name[-1] == alt_name[0]
        if weak:
            alt_name = alt_name[1:-1].strip()
        if alt_name:
            out.setdefault(ent, []).append((alt_name, weak))
    return out


def parse_ofac_add(text: str) -> dict[str, list[str]]:
    """Return ent_num -> address strings, to merge into SDN records."""
    out: dict[str, list[str]] = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 5:
            continue
        ent = _clean(row[0])
        parts = [_clean(row[2]), _clean(row[3]), _clean(row[4])]
        addr = ", ".join(p for p in parts if p)
        if ent and addr:
            out.setdefault(ent, []).append(addr)
    return out


def merge_ofac(
    base: ParseOutcome,
    alts: dict[str, list[tuple[str, bool]]] | None = None,
    adds: dict[str, list[str]] | None = None,
) -> ParseOutcome:
    """Fold ALT and ADD files into the primary SDN records.

    Aliases matter more than anything else in this file set: screening SDN
    primary names alone misses a large share of real hits, because OFAC lists
    the transliteration variants in ALT rather than in the primary record.
    """
    alts = alts or {}
    adds = adds or {}
    matched_alt = 0
    for p in base.parties:
        a = alts.get(p.native_id)
        if a:
            for item in a:
                # Tolerate the pre-weak-alias plain-string shape so a caller
                # feeding a hand-built dict does not silently lose aliases.
                nm, weak = item if isinstance(item, tuple) else (item, False)
                p.aliases.append(nm)
                if weak:
                    p.weak_aliases.append(nm)
            matched_alt += 1
        ad = adds.get(p.native_id)
        if ad:
            p.addresses.extend(ad)
            country_guess = [x.split(",")[-1].strip() for x in ad if "," in x]
            p.countries.extend([c for c in country_guess if c])
    orphan_alt = set(alts) - {p.native_id for p in base.parties}
    if orphan_alt:
        base.warnings.append(
            f"{len(orphan_alt)} ALT entries referenced entity numbers absent "
            "from the primary file. The two files are out of sync -- re-fetch "
            "both from the same publication before relying on this snapshot."
        )
    base.warnings.append(f"Merged alternate names into {matched_alt} records.")
    return base


# --------------------------------------------------------------------------
# BIS
# --------------------------------------------------------------------------

def parse_bis_dpl(text: str) -> ParseOutcome:
    """Parse dpl.txt (tab-delimited, with header)."""
    out = ParseOutcome()
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    if not reader.fieldnames:
        out.warnings.append("DPL file had no header row; nothing parsed.")
        return out
    mapping, unmapped = _build_map(list(reader.fieldnames), BIS_DPL_FIELDS)
    out.unmapped_columns = unmapped
    if "name" not in mapping:
        out.warnings.append(
            f"DPL header has no name column. Headers seen: {reader.fieldnames}"
        )
        return out
    for i, row in enumerate(reader):
        out.row_count += 1
        name = _get(row, mapping, "name")
        if not name:
            out.skipped_rows += 1
            continue
        addr_parts = [
            _get(row, mapping, "addresses"),
            _get(row, mapping, "city"),
            _get(row, mapping, "state"),
            _get(row, mapping, "postal_code"),
        ]
        address = ", ".join(p for p in addr_parts if p)
        fr = _get(row, mapping, "federal_register")
        effective = _get(row, mapping, "effective_date")
        # The file has no identifier column. The uid used to be the row
        # ordinal, so every insertion BIS made shifted every uid below it and
        # a case keyed on DPL:417 in March referred to a different person in
        # April. Derive it from the content that identifies a denial order
        # instead -- name, address, FR citation, effective date -- so the id
        # survives re-publication and only changes when the order does.
        key = "\x1f".join((fold(name), fold(address), fold(fr), effective))
        native = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        out.parties.append(
            ListedParty(
                uid=f"DPL:{native}",
                source="DPL",
                native_id=native,
                name=name,
                party_type="unknown",
                addresses=[address] if address else [],
                countries=[_get(row, mapping, "countries")] if _get(row, mapping, "countries") else [],
                remarks=_get(row, mapping, "action"),
                federal_register=fr,
                effective_date=effective,
                expiration_date=_get(row, mapping, "expiration_date"),
                raw=_safe_raw(row),
            )
        )
    return out


def parse_bis_entity(text: str, source_code: str = "EL") -> ParseOutcome:
    """Parse a BIS Entity/UVL/MEU CSV export."""
    out = ParseOutcome()
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        out.warnings.append(f"{source_code} file had no header row; nothing parsed.")
        return out
    mapping, unmapped = _build_map(list(reader.fieldnames), BIS_ENTITY_FIELDS)
    out.unmapped_columns = unmapped
    if "name" not in mapping:
        out.warnings.append(
            f"{source_code} header has no name column. Headers: {reader.fieldnames}"
        )
        return out
    for i, row in enumerate(reader):
        out.row_count += 1
        name = _get(row, mapping, "name")
        if not name:
            out.skipped_rows += 1
            continue
        native = _get(row, mapping, "native_id") or str(i)
        remarks = []
        for extra in ("license_requirement", "license_policy"):
            v = _get(row, mapping, extra)
            if v:
                remarks.append(f"{extra.replace('_', ' ')}: {v}")
        out.parties.append(
            ListedParty(
                uid=f"{source_code}:{native}",
                source=source_code,
                native_id=native,
                name=name,
                party_type="entity",
                aliases=_split_multi(_get(row, mapping, "aliases")),
                addresses=_split_multi(_get(row, mapping, "addresses")),
                countries=_split_multi(_get(row, mapping, "countries")),
                remarks=" | ".join(remarks),
                federal_register=_get(row, mapping, "federal_register"),
                effective_date=_get(row, mapping, "effective_date"),
                raw=_safe_raw(row),
            )
        )
    return out


PARSERS = {
    "csl": parse_csl,
    "csl_subset": parse_csl_subset,
    "ofac_sdn": parse_ofac_sdn,
    "ofac_alt": parse_ofac_alt,
    "ofac_add": parse_ofac_add,
    "bis_dpl": parse_bis_dpl,
    "bis_entity": parse_bis_entity,
}


def _merge_unique(into: list[str], extra: list[str]) -> None:
    seen = {x.lower() for x in into}
    into.extend(x for x in extra if x.lower() not in seen)


def dedupe(parties: list[ListedParty]) -> list[ListedParty]:
    """Collapse duplicate uids, merging every list-valued field.

    CSL plus the primary OFAC files legitimately describe the same party
    twice. Keeping both would double-count hits in the report; dropping one
    blindly would lose whichever file had the richer alias set.

    Every list field is merged, not only the name-bearing ones. The first
    version merged aliases, addresses and countries and silently kept the
    first record's programs, ids and party type -- so whichever file loaded
    first decided whether the adjudicator saw a date of birth, whether the
    program tag that changes the legal effect (FSE, SSI) survived, and
    whether an SDN entity was screened as "unknown" and lost its 50 Percent
    Rule flag.
    """
    by_uid: dict[str, ListedParty] = {}
    for p in parties:
        cur = by_uid.get(p.uid)
        if cur is None:
            by_uid[p.uid] = p
            continue
        for fld in ("aliases", "weak_aliases", "addresses", "countries", "programs", "ids"):
            _merge_unique(getattr(cur, fld), getattr(p, fld))
        # A known party type is evidence; "unknown" is the absence of it.
        if cur.party_type == "unknown" and p.party_type != "unknown":
            cur.party_type = p.party_type
        for fld in ("remarks", "federal_register", "effective_date",
                    "expiration_date", "source_url"):
            if not getattr(cur, fld):
                setattr(cur, fld, getattr(p, fld))
    return list(by_uid.values())
