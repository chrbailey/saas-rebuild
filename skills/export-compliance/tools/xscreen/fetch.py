"""Acquire government list files and record exactly where they came from.

The manifest this writes is the reason a screening result is defensible. It
records, per file: the URL actually used, the HTTP status, the fetch
timestamp, the byte count, the SHA-256, the parsed row count, and any columns
the parser did not recognize. A regulator asking "what did you screen against
on 12 March" gets a hash, not a shrug.

Failure posture is fail-loud. A source that will not download is recorded as
an error and the run is marked degraded; it is never silently skipped, and a
stale cache is never presented as fresh. `MAX_LIST_AGE_DAYS` is enforced at
screening time, not here, so an operator can deliberately re-screen against a
historical snapshot for an audit.
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import SCHEMA_VERSION, ListedParty, stable_digest
from .normalize import (
    ParseOutcome,
    dedupe,
    merge_ofac,
    parse_bis_dpl,
    parse_bis_entity,
    parse_csl,
    parse_csl_subset,
    parse_ofac_add,
    parse_ofac_alt,
    parse_ofac_sdn,
)
from .sources import BY_CODE, DEFAULT_REFRESH, MAX_LIST_AGE_DAYS, Source

USER_AGENT = (
    "xscreen/1.0 (export-compliance screening; contact your compliance officer)"
)
TIMEOUT_S = 120


@dataclass
class FileRecord:
    code: str
    url: str = ""
    http_status: int = 0
    fetched_at: str = ""
    bytes: int = 0
    sha256: str = ""
    rows_parsed: int = 0
    rows_skipped: int = 0
    parties: int = 0
    unmapped_columns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    from_cache: bool = False

    @property
    def ok(self) -> bool:
        return not self.error and self.parties > 0


@dataclass
class Manifest:
    created_at: str
    engine_version: str
    files: list[dict] = field(default_factory=list)
    total_parties: int = 0
    degraded: bool = False
    degraded_reason: str = ""
    digest: str = ""
    covered_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _ssl_context() -> ssl.SSLContext:
    """Honour the environment's CA bundle. Never disable verification."""
    ca = (
        os.environ.get("XSCREEN_CA_BUNDLE")
        or os.environ.get("REQUESTS_CA_BUNDLE")
        or os.environ.get("SSL_CERT_FILE")
    )
    if ca and Path(ca).exists():
        return ssl.create_default_context(cafile=ca)
    return ssl.create_default_context()


def download(url: str) -> tuple[bytes, int]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=_ssl_context()) as resp:
        return resp.read(), resp.status


def fetch_source(src: Source, dest: Path) -> FileRecord:
    """Try each registered URL in order; record the one that worked."""
    rec = FileRecord(code=src.code)
    errors: list[str] = []
    for url in src.urls:
        try:
            body, status = download(url)
        except urllib.error.HTTPError as e:
            errors.append(f"{url} -> HTTP {e.code}")
            continue
        except Exception as e:  # noqa: BLE001 - report every transport failure
            errors.append(f"{url} -> {type(e).__name__}: {e}")
            continue
        if status != 200 or not body:
            errors.append(f"{url} -> status {status}, {len(body)} bytes")
            continue
        rec.url = url
        rec.http_status = status
        rec.bytes = len(body)
        rec.sha256 = hashlib.sha256(body).hexdigest()
        rec.fetched_at = datetime.now(timezone.utc).isoformat()
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{src.code}.raw").write_bytes(body)
        return rec
    rec.error = "; ".join(errors) or "no URLs configured"
    return rec


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_cached(code: str, data_dir: Path) -> tuple[list[ListedParty], ParseOutcome]:
    """Parse an already-downloaded raw file into canonical parties."""
    src = BY_CODE[code]
    path = data_dir / f"{code}.raw"
    if not path.exists():
        out = ParseOutcome()
        out.warnings.append(f"No cached file for {code} at {path}")
        return [], out
    text = _decode(path.read_bytes())

    if src.parser == "csl":
        out = parse_csl(text)
    elif src.parser == "csl_subset":
        out = parse_csl_subset(text, code)
    elif src.parser == "bis_dpl":
        out = parse_bis_dpl(text)
    elif src.parser == "bis_entity":
        out = parse_bis_entity(text, code)
    elif src.parser == "ofac_sdn":
        out = parse_ofac_sdn(text, "SDN" if code == "SDN" else "NONSDN")
        # Fold in the alias and address side files when present.
        alt_path = data_dir / "SDN_ALT.raw"
        add_path = data_dir / "SDN_ADD.raw"
        if code == "SDN":
            alts = parse_ofac_alt(_decode(alt_path.read_bytes())) if alt_path.exists() else {}
            adds = parse_ofac_add(_decode(add_path.read_bytes())) if add_path.exists() else {}
            if not alts:
                out.warnings.append(
                    "SDN loaded WITHOUT the alternate-names file. Recall is "
                    "materially reduced -- OFAC publishes most transliteration "
                    "variants in ALT.CSV, not in the primary record."
                )
            out = merge_ofac(out, alts, adds)
    elif src.parser in ("ofac_alt", "ofac_add"):
        # Side files carry no standalone parties; they merge into SDN.
        return [], ParseOutcome()
    else:
        out = ParseOutcome()
        out.warnings.append(f"No parser registered for {code}")
    return out.parties, out


def refresh(
    data_dir: Path,
    codes: tuple[str, ...] = DEFAULT_REFRESH,
    offline: bool = False,
) -> Manifest:
    """Download (unless offline) and parse the requested sources."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(
        created_at=datetime.now(timezone.utc).isoformat(),
        engine_version=SCHEMA_VERSION,
    )
    records: list[FileRecord] = []
    all_parties: list[ListedParty] = []

    # (code, sha256) -> the fetch time already on record for that exact
    # content, so an offline re-parse cannot present old data as new.
    prior_fetched: dict[tuple[str, str], str] = {}
    try:
        for f in load_manifest(data_dir).files:
            if f.get("sha256") and f.get("fetched_at") and not f.get("error"):
                prior_fetched[(f.get("code", ""), f["sha256"])] = f["fetched_at"]
    except (FileNotFoundError, ValueError):
        pass

    # Side files must be present before SDN is parsed.
    ordered = sorted(codes, key=lambda c: 0 if c in ("SDN_ALT", "SDN_ADD") else 1)

    for code in ordered:
        src = BY_CODE.get(code)
        if src is None:
            rec = FileRecord(code=code, error=f"unknown source code {code!r}")
            records.append(rec)
            continue
        if offline:
            rec = FileRecord(code=code)
            path = data_dir / f"{code}.raw"
            if path.exists():
                body = path.read_bytes()
                rec.url = "(cached)"
                rec.http_status = 0
                rec.bytes = len(body)
                rec.sha256 = hashlib.sha256(body).hexdigest()
                rec.from_cache = True
                # Freshness must describe when this CONTENT was obtained, not
                # when the file was last touched. Deriving it from st_mtime
                # made the staleness refusal a one-line shell bypass:
                # `touch lists/*.raw` turned three-year-old sanctions data into
                # a "0.0 days old" snapshot, with stale_override false in the
                # audit log. Carry forward the recorded fetch time for this
                # exact sha256 instead, and only fall back to mtime when there
                # is no prior record to carry.
                prior = prior_fetched.get((code, rec.sha256))
                if prior:
                    rec.fetched_at = prior
                else:
                    rec.fetched_at = datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).isoformat()
                    rec.warnings.append(
                        f"No prior manifest entry for this {code} content; fetch "
                        "time was inferred from the file timestamp and may be "
                        "later than when the data was actually published."
                    )
            else:
                rec.error = f"offline and no cached file at {path}"
        else:
            rec = fetch_source(src, data_dir)

        if not rec.error:
            parties, out = parse_cached(code, data_dir)
            rec.rows_parsed = out.row_count
            rec.rows_skipped = out.skipped_rows
            rec.parties = len(parties)
            rec.unmapped_columns = out.unmapped_columns
            rec.warnings = out.warnings
            all_parties.extend(parties)
        records.append(rec)

    merged = dedupe(all_parties)
    manifest.files = [asdict(r) for r in records]
    manifest.total_parties = len(merged)

    failed = [r.code for r in records if r.error]
    empty = [r.code for r in records if not r.error and r.parties == 0
             and r.code not in ("SDN_ALT", "SDN_ADD")]
    # A refresh narrower than the default set rewrites parties.jsonl from only
    # the codes it was given. `xscreen refresh --sources DPL` is a reasonable
    # thing to type and it silently dropped the SDN list, after which a
    # blocked party screened CLEAR and the CLI exited 0 -- with the manifest
    # reporting fresh and not degraded. Coverage is now part of the manifest,
    # and pipeline.run() refuses to screen without it.
    missing_default = [c for c in DEFAULT_REFRESH if c not in set(codes)]
    if failed or empty or missing_default:
        manifest.degraded = True
        bits = []
        if failed:
            bits.append(f"sources failed to download: {failed}")
        if empty:
            bits.append(f"sources downloaded but yielded no parties: {empty}")
        if missing_default:
            bits.append(
                f"refresh covered {sorted(set(codes))}, which omits {missing_default} "
                "from the default set -- the party corpus was rebuilt from the "
                "narrower set and is NOT a complete screening corpus"
            )
        manifest.degraded_reason = "; ".join(bits)
    manifest.covered_sources = sorted(
        {r.code for r in records if not r.error and r.code not in ("SDN_ALT", "SDN_ADD")}
    )

    manifest.digest = stable_digest(
        {"files": [{"code": r.code, "sha256": r.sha256} for r in records],
         "total": manifest.total_parties}
    )

    (data_dir / "manifest.json").write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "parties.jsonl").write_text(
        "\n".join(json.dumps(p.to_dict(), ensure_ascii=False) for p in merged),
        encoding="utf-8",
    )
    return manifest


def load_parties(data_dir: Path) -> list[ListedParty]:
    path = Path(data_dir) / "parties.jsonl"
    if not path.exists():
        raise FileNotFoundError(
            f"No party corpus at {path}. Run `xscreen refresh` first."
        )
    out: list[ListedParty] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(ListedParty.from_dict(json.loads(line)))
    return out


def load_manifest(data_dir: Path) -> Manifest:
    path = Path(data_dir) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"No manifest at {path}. Run `xscreen refresh` first.")
    d = json.loads(path.read_text(encoding="utf-8"))
    m = Manifest(
        created_at=d.get("created_at", ""),
        engine_version=d.get("engine_version", ""),
        files=d.get("files", []),
        total_parties=d.get("total_parties", 0),
        degraded=d.get("degraded", False),
        degraded_reason=d.get("degraded_reason", ""),
        digest=d.get("digest", ""),
        covered_sources=d.get("covered_sources", []),
    )
    return m


def age_days(manifest: Manifest, now: datetime | None = None) -> float:
    """Age of the *oldest successfully fetched* file, in days.

    Taking the oldest rather than the manifest timestamp is deliberate: a
    refresh that re-downloaded four of five sources and fell back to a cached
    fifth must report the age of that fifth file.
    """
    now = now or datetime.now(timezone.utc)
    stamps: list[datetime] = []
    for f in manifest.files:
        ts = f.get("fetched_at")
        if not ts or f.get("error"):
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        stamps.append(dt)
    if not stamps:
        return float("inf")
    return (now - min(stamps)).total_seconds() / 86400.0


def corpus_check(manifest: Manifest) -> tuple[bool, str]:
    """(ok, message) for corpus COMPLETENESS. Not overridable.

    Deliberately separate from `staleness_check`. `--allow-stale` exists so an
    operator can deliberately re-screen against a historical snapshot for an
    audit -- a considered act on data they know is old but *whole*. It must not
    also wave through a corpus that is missing entire lists, because that is
    not a considered act, it is the false clear this system exists to prevent:
    a party that appears only on the omitted list comes back CLEAR.

    Age is a judgement the operator may make. Completeness is not.
    """
    missing = [c for c in DEFAULT_REFRESH
               if c not in set(manifest.covered_sources or []) and c not in ("SDN_ALT", "SDN_ADD")]
    if manifest.covered_sources and missing:
        return False, (
            f"The loaded corpus does not cover {missing}. It was built by a "
            "narrower refresh and is not a complete screening corpus -- a party "
            "listed only on a missing list would screen CLEAR. Run "
            "`xscreen refresh` with the default source set."
        )
    if manifest.degraded:
        return False, f"Manifest is degraded: {manifest.degraded_reason}"
    return True, f"Corpus covers {manifest.covered_sources or 'unknown sources'}."


def staleness_check(manifest: Manifest, max_age_days: int = MAX_LIST_AGE_DAYS,
                    now: datetime | None = None) -> tuple[bool, str]:
    """(ok, message) for list AGE only.

    A False here is overridable with `--allow-stale`, and the override is
    recorded in the audit log. Completeness lives in `corpus_check` precisely
    so that override cannot reach it.
    """
    a = age_days(manifest, now)
    if a == float("inf"):
        return False, "No successfully fetched source files in the manifest."
    if a < 0:
        # A future timestamp made `a > max_age_days` permanently false, so a
        # hand-edited manifest or a skewed clock read as eternally fresh.
        return False, (
            f"Manifest timestamps are {abs(a):.1f} days in the future. Either the "
            "system clock is wrong or the manifest was edited; neither is a "
            "basis for screening."
        )
    if a > max_age_days:
        return False, (
            f"List data is {a:.1f} days old (limit {max_age_days}). Government "
            "lists change weekly or faster; screening against a stale snapshot "
            "produces a false clear. Run `xscreen refresh`."
        )
    return True, f"List data is {a:.1f} days old across {len(manifest.files)} sources."
