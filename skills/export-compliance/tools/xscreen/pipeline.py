"""End-to-end screening run: party file in, adjudicated results out.

Order is fixed and matters:

    load lists -> deterministic match -> deterministic rules -> provisional
    disposition -> LLM adjudication -> critic loop -> final disposition -> audit

Everything before the LLM step is reproducible from the inputs alone. If the
model stage is disabled or unavailable, the run still completes and every case
with a candidate routes to a human. A screening run that cannot reach a model
must still produce a usable, auditable result -- that is what makes this
deployable in a network with no outbound access.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from .adjudicate import adjudicate_result, resolve_disposition
from .audit import AuditLog
from .critic import CriticReview, Route, run_loop
from .fetch import Manifest, load_manifest, load_parties, staleness_check
from .llm import Backend
from .match import ListIndex, screen_name
from .models import ScreeningResult, SubjectParty
from .rules import Policy, evaluate, load_policy

SUBJECT_FIELDS: dict[str, tuple[str, ...]] = {
    "ref": ("ref", "id", "row_id", "account", "account_number", "customer_id", "reference"),
    "name": ("name", "party", "party_name", "customer", "customer_name", "vendor",
             "vendor_name", "company", "company_name", "consignee", "end_user"),
    "aliases": ("aliases", "alias", "aka", "dba", "trade_name", "also_known_as"),
    "party_type": ("party_type", "type", "entity_type"),
    "country": ("country", "party_country", "ship_to_country"),
    "address": ("address", "street", "full_address", "ship_to_address"),
    "role": ("role", "party_role", "relationship"),
    "destination_country": ("destination_country", "destination", "ultimate_destination",
                            "ship_to", "final_destination"),
    "eccn": ("eccn", "classification", "ccl"),
    "item_description": ("item_description", "item", "product", "description", "commodity"),
    "end_use": ("end_use", "enduse", "intended_use", "application"),
}


def _norm(h: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def parse_party_file(text: str) -> tuple[list[SubjectParty], list[str]]:
    """Parse an operator CSV into subjects. Returns (subjects, warnings)."""
    warnings: list[str] = []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["Party file has no header row."]
    norm = {_norm(h): h for h in reader.fieldnames}
    mapping: dict[str, str] = {}
    for canon, aliases in SUBJECT_FIELDS.items():
        for a in aliases:
            if a in norm:
                mapping[canon] = norm[a]
                break
    if "name" not in mapping:
        return [], [
            "Party file has no recognizable name column. Expected one of: "
            f"{', '.join(SUBJECT_FIELDS['name'])}. Saw: {reader.fieldnames}"
        ]
    unmapped = [h for h in reader.fieldnames if h not in set(mapping.values())]
    if unmapped:
        warnings.append(
            f"Columns carried through as raw context but not screened directly: {unmapped}"
        )

    subjects: list[SubjectParty] = []
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        def g(k: str) -> str:
            h = mapping.get(k)
            return (row.get(h) or "").strip() if h else ""
        name = g("name")
        if not name:
            warnings.append(f"Row {i}: blank name, skipped.")
            continue
        aliases = [a.strip() for a in g("aliases").replace("|", ";").split(";") if a.strip()]
        subjects.append(SubjectParty(
            ref=g("ref") or f"row{i}",
            name=name,
            aliases=aliases,
            party_type=(g("party_type") or "unknown").lower() if g("party_type") in
            ("individual", "entity", "vessel", "aircraft") else "unknown",  # type: ignore[arg-type]
            country=g("country"),
            address=g("address"),
            role=g("role"),
            destination_country=g("destination_country") or g("country"),
            eccn=g("eccn"),
            item_description=g("item_description"),
            end_use=g("end_use"),
            raw={k: v for k, v in row.items() if v and v.strip()},
        ))
    return subjects, warnings


def build_index(data_dir: Path) -> tuple[ListIndex, Manifest]:
    manifest = load_manifest(data_dir)
    index = ListIndex()
    index.add_all(load_parties(data_dir))
    return index.build(), manifest


def screen_subject(
    subject: SubjectParty,
    index: ListIndex,
    manifest: Manifest,
    policy: Policy,
    as_of: date,
) -> ScreeningResult:
    """Deterministic half only. No model involved."""
    candidates = screen_name(subject, index)
    result = ScreeningResult(
        subject=subject.to_dict(),
        candidates=[c.to_dict() for c in candidates],
        list_manifest_digest=manifest.digest,
        screened_at=datetime.now(timezone.utc).isoformat(),
    )
    result.rule_flags = [f.to_dict() for f in evaluate(subject, candidates, policy, as_of)]
    from .rules import provisional_disposition
    result.disposition, result.disposition_reason = provisional_disposition(result)  # type: ignore[assignment]
    result.requires_human = result.disposition != "CLEAR"
    return result


def run(
    subjects: Iterable[SubjectParty],
    data_dir: Path,
    audit_path: Path,
    use_llm: bool = True,
    use_critic: bool = True,
    backend: Backend | None = None,
    critic_backend: Backend | None = None,
    as_of: date | None = None,
    allow_stale: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> tuple[list[ScreeningResult], dict]:
    """Screen every subject. Returns (results, run_summary)."""
    data_dir, audit_path = Path(data_dir), Path(audit_path)
    index, manifest = build_index(data_dir)
    policy = load_policy()
    as_of = as_of or date.today()
    log = AuditLog(audit_path)

    fresh, staleness_msg = staleness_check(manifest)
    if not fresh and not allow_stale:
        raise RuntimeError(
            f"Refusing to screen: {staleness_msg} Re-run `xscreen refresh`, or "
            "pass --allow-stale to proceed deliberately (the override is recorded "
            "in the audit log)."
        )

    subjects = list(subjects)
    run_started = datetime.now(timezone.utc).isoformat()
    start_entry = log.append("run.start", {
        "subjects": len(subjects),
        "list_manifest_digest": manifest.digest,
        "list_total_parties": manifest.total_parties,
        "list_files": [
            {"code": f.get("code"), "sha256": f.get("sha256"), "fetched_at": f.get("fetched_at"),
             "url": f.get("url"), "error": f.get("error")}
            for f in manifest.files
        ],
        "staleness": staleness_msg,
        "stale_override": (not fresh) and allow_stale,
        "policy_as_of": policy.as_of,
        "policy_verified": policy.verified,
        "llm_enabled": use_llm,
        "critic_enabled": use_critic,
        "as_of_date": as_of.isoformat(),
    })

    results: list[ScreeningResult] = []
    routes: list[Route] = []
    all_reviews: list[CriticReview] = []

    for i, s in enumerate(subjects, 1):
        if progress:
            progress(i, len(subjects), s.name)
        result = screen_subject(s, index, manifest, policy, as_of)

        has_candidates = any(c.get("band") != "NONE" for c in result.candidates)
        if has_candidates:
            if use_llm and use_critic:
                def _adj(r: ScreeningResult, brief: str) -> ScreeningResult:
                    r = adjudicate_result(r, backend, enabled=True)
                    if brief:
                        for a in r.adjudications:
                            a["retry_context"] = brief[:800]
                    return resolve_disposition(r)

                result, reviews, rt = run_loop(result, _adj, critic_backend)
                routes.append(rt)
                all_reviews.extend(reviews)
            else:
                result = adjudicate_result(result, backend, enabled=use_llm)
                result = resolve_disposition(result)

        log.append("case.screened", {
            "ref": s.ref,
            "name": s.name,
            "candidate_count": sum(1 for c in result.candidates if c.get("band") != "NONE"),
            "top_band": result.top_band(),
            "rule_flag_ids": [f.get("rule_id") for f in result.rule_flags],
            "disposition": result.disposition,
            "disposition_reason": result.disposition_reason,
            "requires_human": result.requires_human,
            "adjudication_models": sorted({a.get("model", "") for a in result.adjudications}),
            "critic_finding_count": len(result.critic_findings),
        })
        results.append(result)

    counts: dict[str, int] = {}
    for r in results:
        counts[r.disposition] = counts.get(r.disposition, 0) + 1

    summary = {
        "started_at": run_started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "subjects": len(subjects),
        "dispositions": counts,
        "requires_human": sum(1 for r in results if r.requires_human),
        "list_manifest_digest": manifest.digest,
        "list_parties": manifest.total_parties,
        "list_staleness": staleness_msg,
        "policy_as_of": policy.as_of,
        "policy_verified": policy.verified,
        "llm_enabled": use_llm,
        "critic_enabled": use_critic,
        "critic_routes": {a: sum(1 for r in routes if r.action == a)
                          for a in ("COMMIT", "RETRY", "ESCALATE")} if routes else {},
        "critic_infra_errors": sum(1 for r in all_reviews if r.infra_error),
        "audit_start_seq": start_entry["seq"],
    }
    end_entry = log.append("run.end", summary)
    summary["audit_end_seq"] = end_entry["seq"]
    summary["audit_head_hash"] = end_entry["hash"]
    return results, summary
