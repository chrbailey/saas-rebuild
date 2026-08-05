"""Render screening results for the three audiences that read them.

* **The operator** needs a worklist: what to look at, worst first.
* **Counsel** needs the basis: which list, which authority, what obligation,
  and what the record does not establish.
* **The auditor** needs provenance: which snapshot, which hashes, what was
  overridden and by whom.

One document serves all three, in that order, because the operator reads it
today and the auditor reads it in four years.
"""

from __future__ import annotations

import csv
import io
from typing import Sequence

from .models import ScreeningResult

DISPOSITION_ORDER = {"BLOCKED": 0, "ESCALATE": 1, "CONFIRMED_HIT": 2, "REVIEW": 3, "CLEAR": 4}
SEVERITY_ORDER = {"prohibitive": 0, "license": 1, "diligence": 2, "informational": 3}


def _esc(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def summary_csv(results: Sequence[ScreeningResult]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([
        "ref", "name", "disposition", "requires_human", "top_band",
        "top_list", "top_matched_name", "top_score", "rule_flags",
        "prohibitive_flags", "adjudication", "critic_findings", "screened_at",
        "list_manifest_digest",
    ])
    for r in sorted(results, key=lambda x: (DISPOSITION_ORDER.get(x.disposition, 9), x.subject.get("ref", ""))):
        live = [c for c in r.candidates if c.get("band") != "NONE"]
        top = live[0] if live else {}
        verdicts = sorted({a.get("verdict", "") for a in r.adjudications}) if r.adjudications else []
        prohibitive = [f.get("rule_id") for f in r.rule_flags if f.get("severity") == "prohibitive"]
        w.writerow([
            r.subject.get("ref", ""),
            r.subject.get("name", ""),
            r.disposition,
            "yes" if r.requires_human else "no",
            r.top_band(),
            top.get("listed_source", ""),
            top.get("listed_name", ""),
            top.get("score", ""),
            ";".join(f.get("rule_id", "") for f in r.rule_flags),
            ";".join(p for p in prohibitive if p),
            ";".join(verdicts),
            len(r.critic_findings),
            r.screened_at,
            r.list_manifest_digest,
        ])
    return buf.getvalue()


def markdown_report(results: Sequence[ScreeningResult], summary: dict) -> str:
    counts = summary.get("dispositions", {})
    lines: list[str] = []
    a = lines.append

    a("# Restricted Party Screening Report")
    a("")
    a(f"**Run:** {summary.get('started_at', '')} to {summary.get('finished_at', '')}  ")
    a(f"**Parties screened:** {summary.get('subjects', 0)}  ")
    a(f"**Requires human review:** {summary.get('requires_human', 0)}")
    a("")

    # ---- Worklist ------------------------------------------------------
    a("## Disposition summary")
    a("")
    a("| Disposition | Count | Meaning |")
    a("|---|---|---|")
    meanings = {
        "BLOCKED": "Confirmed hit and a prohibitive rule applies. Do not proceed.",
        "ESCALATE": "Unresolved after review. A human must decide.",
        "CONFIRMED_HIT": "Adjudicated as the listed party. Confirm and determine the obligation.",
        "REVIEW": "Candidates or obligations outstanding. Analyst review required.",
        "CLEAR": "No candidate above the review floor and no outstanding obligation.",
    }
    for d in sorted(counts, key=lambda x: DISPOSITION_ORDER.get(x, 9)):
        a(f"| {d} | {counts[d]} | {meanings.get(d, '')} |")
    a("")

    actionable = [r for r in results if r.disposition != "CLEAR"]
    if actionable:
        a("## Worklist")
        a("")
        a("Worst first. Every row needs a documented human decision.")
        a("")
        a("| Ref | Counterparty | Disposition | Top match | List | Band | Score | Why |")
        a("|---|---|---|---|---|---|---|---|")
        for r in sorted(actionable, key=lambda x: (DISPOSITION_ORDER.get(x.disposition, 9),
                                                   -_top_score(x))):
            live = [c for c in r.candidates if c.get("band") != "NONE"]
            top = live[0] if live else {}
            a("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
                _esc(r.subject.get("ref", "")),
                _esc(r.subject.get("name", "")),
                r.disposition,
                _esc(top.get("listed_name", "-")),
                top.get("listed_source", "-"),
                top.get("band", "-"),
                top.get("score", "-"),
                _esc(r.disposition_reason),
            ))
        a("")

    # ---- Case detail ---------------------------------------------------
    if actionable:
        a("## Case detail")
        a("")
    for r in sorted(actionable, key=lambda x: DISPOSITION_ORDER.get(x.disposition, 9)):
        subj = r.subject
        a(f"### {subj.get('ref', '')} — {subj.get('name', '')}")
        a("")
        a(f"**Disposition:** {r.disposition} — {r.disposition_reason}")
        a("")
        ctx = [f"{k}: {subj.get(k)}" for k in
               ("country", "destination_country", "role", "eccn", "item_description", "end_use")
               if subj.get(k)]
        if ctx:
            a(f"**Transaction context:** {'; '.join(ctx)}")
            a("")

        live = [c for c in r.candidates if c.get("band") != "NONE"]
        if live:
            a("**Candidate matches**")
            a("")
            a("| List | Matched name | Band | Score | Adjudication | Legal effect |")
            a("|---|---|---|---|---|---|")
            adj_by = {x.get("listed_uid"): x for x in r.adjudications}
            for c in live:
                adj = adj_by.get(c.get("listed_uid"), {})
                verdict = adj.get("verdict", "not adjudicated")
                if adj.get("guardrail_override"):
                    verdict += " (guardrail applied)"
                a("| {} | {} | {} | {} | {} | {} |".format(
                    c.get("listed_source", ""),
                    _esc(c.get("listed_name", "")),
                    c.get("band", ""),
                    c.get("score", ""),
                    _esc(verdict),
                    _esc((c.get("legal_effect") or "")[:220]),
                ))
            a("")
            for c in live:
                adj = adj_by.get(c.get("listed_uid"))
                if adj and adj.get("rationale"):
                    a(f"- **{_esc(c.get('listed_name',''))}** — {_esc(adj['rationale'])}")
                    if adj.get("guardrail_override"):
                        a(f"  - Guardrail: {_esc(adj['guardrail_override'])}")
            a("")

        if r.rule_flags:
            a("**Obligations and flags**")
            a("")
            a("| Severity | Rule | Basis | Action required |")
            a("|---|---|---|---|")
            for f in sorted(r.rule_flags, key=lambda x: SEVERITY_ORDER.get(x.get("severity", ""), 9)):
                marker = " ⚠ unverified policy" if f.get("unverified_policy") else ""
                a("| {} | {} | {} | {} |".format(
                    f.get("severity", ""),
                    _esc(f.get("title", "")) + marker,
                    _esc(f.get("basis", "")),
                    _esc(f.get("action_required", "")),
                ))
            a("")

        if r.critic_findings:
            a("**Independent review findings**")
            a("")
            for f in r.critic_findings:
                a(f"- [{f.get('severity')}] {_esc(f.get('finding',''))} "
                  f"→ {_esc(f.get('suggested_action',''))}")
            a("")

    # ---- Provenance ----------------------------------------------------
    a("## Provenance and limitations")
    a("")
    a(f"- **List snapshot digest:** `{summary.get('list_manifest_digest','')}`")
    a(f"- **Listed parties loaded:** {summary.get('list_parties', 0)}")
    a(f"- **List freshness:** {summary.get('list_staleness','')}")
    a(f"- **Country policy file as of:** {summary.get('policy_as_of','')} "
      f"({'verified by operator' if summary.get('policy_verified') else '**NOT operator-verified**'})")
    a(f"- **Machine adjudication:** {'enabled' if summary.get('llm_enabled') else 'disabled — every candidate routed to a human'}")
    a(f"- **Independent critic review:** {'enabled' if summary.get('critic_enabled') else 'disabled'}")
    if summary.get("critic_routes"):
        a(f"- **Critic routing:** {summary['critic_routes']}")
    if summary.get("critic_infra_errors"):
        a(f"- **Critic infrastructure errors:** {summary['critic_infra_errors']} "
          "(these were routed to human review, never treated as passes)")
    a(f"- **Audit log entries:** {summary.get('audit_start_seq','?')}–{summary.get('audit_end_seq','?')}, "
      f"head hash `{summary.get('audit_head_hash','')}`")
    a("")
    a("**What this run does not establish.**")
    a("")
    a("- **Ownership.** Entities owned 50 percent or more, directly or "
      "indirectly, in the aggregate, by blocked persons are themselves blocked "
      "under OFAC's 50 Percent Rule and appear on no list. There is no name to "
      "match. A parallel BIS Affiliates Rule covers Entity List, MEU and "
      "denial-order parties; confirm its current status.")
    a("- **Classification.** Whether a licence is required depends on the "
      "item's ECCN, which this run does not determine.")
    a("- **Entity List scope.** A licence requirement is scoped to the items "
      "named in that entry, and footnote designations can trigger a Foreign "
      "Direct Product Rule. Read the entry.")
    a("- **End-use and end-user controls on unlisted parties.** 15 CFR 744.21 "
      "reaches military end users in the destinations it names whether or not "
      "they appear on the MEU List.")
    a("- **Deemed exports.** Releasing controlled technology to a foreign "
      "national inside the United States is an export to their home country. "
      "No shipment occurs and no counterparty is screened, so nothing in this "
      "pipeline can see it.")
    a("- **Non-U.S. regimes.** Only U.S. government lists are screened. EU, "
      "UK, UN and other national lists are not covered.")
    a("- **Primary publications.** No hit here substitutes for reading the "
      "list entry and the Federal Register notice behind it.")
    a("")
    a("Machine adjudication is advisory; no case here has been cleared on "
      "model judgement alone.")
    a("")
    a("*Not legal advice. Produced by an automated screening tool for the use "
      "of the operator's compliance function.*")
    return "\n".join(lines)


def _top_score(r: ScreeningResult) -> float:
    live = [c for c in r.candidates if c.get("band") != "NONE"]
    return float(live[0].get("score", 0)) if live else 0.0


# --------------------------------------------------------------------------
# Cross-run comparison
# --------------------------------------------------------------------------
# Two workflows the skill treats as central and which need a tool, not a
# suggestion: re-screening the book after a list change (what became a hit
# that was clear last week?) and the parallel run against an incumbent
# system during a migration (where do the two disagree, and which is right?).

NEW_HIT = "NEW_HIT"
RESOLVED = "RESOLVED"
CHANGED = "CHANGED"
ADDED = "ADDED"
REMOVED = "REMOVED"
UNCHANGED = "UNCHANGED"


def load_dispositions(text: str) -> dict[str, dict[str, str]]:
    """Parse a dispositions.csv into {ref: row}."""
    out: dict[str, dict[str, str]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        ref = (row.get("ref") or "").strip()
        if ref:
            out[ref] = row
    return out


def diff_dispositions(before: dict[str, dict[str, str]],
                      after: dict[str, dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Categorize what changed between two screening runs.

    NEW_HIT is the category that matters: a party that was clear and is not
    any more. That is the entire reason to re-screen a book of business after
    a list update, and the reason a party cleared in March must be screened
    again in April.
    """
    groups: dict[str, list[dict[str, str]]] = {
        NEW_HIT: [], RESOLVED: [], CHANGED: [], ADDED: [], REMOVED: [], UNCHANGED: [],
    }
    for ref, new in after.items():
        old = before.get(ref)
        nd = new.get("disposition", "")
        if old is None:
            groups[ADDED if nd == "CLEAR" else NEW_HIT].append(
                {"ref": ref, "name": new.get("name", ""), "before": "(not screened)",
                 "after": nd, "top_list": new.get("top_list", ""),
                 "top_matched_name": new.get("top_matched_name", "")})
            continue
        od = old.get("disposition", "")
        if od == nd:
            groups[UNCHANGED].append({"ref": ref, "name": new.get("name", ""),
                                      "before": od, "after": nd})
            continue
        row = {"ref": ref, "name": new.get("name", ""), "before": od, "after": nd,
               "top_list": new.get("top_list", ""),
               "top_matched_name": new.get("top_matched_name", "")}
        if od == "CLEAR" and nd != "CLEAR":
            groups[NEW_HIT].append(row)
        elif od != "CLEAR" and nd == "CLEAR":
            groups[RESOLVED].append(row)
        else:
            groups[CHANGED].append(row)
    for ref, old in before.items():
        if ref not in after:
            groups[REMOVED].append({"ref": ref, "name": old.get("name", ""),
                                    "before": old.get("disposition", ""),
                                    "after": "(not screened)"})
    return groups


def diff_report(groups: dict[str, list[dict[str, str]]],
                before_label: str, after_label: str) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Screening comparison")
    a("")
    a(f"**Before:** {before_label}  ")
    a(f"**After:** {after_label}")
    a("")

    order = [
        (NEW_HIT, "New hits", "Clear before, not clear now. Investigate every one."),
        (CHANGED, "Changed disposition", "Non-clear before and after, but different."),
        (RESOLVED, "No longer hitting", "Confirm why before accepting a clear."),
        (ADDED, "Newly screened, clear", ""),
        (REMOVED, "No longer in the party file", "Confirm the party is genuinely gone."),
    ]
    a("| Category | Count | Meaning |")
    a("|---|---|---|")
    for key, title, meaning in order:
        a(f"| {title} | {len(groups[key])} | {meaning} |")
    a(f"| Unchanged | {len(groups[UNCHANGED])} | |")
    a("")

    for key, title, meaning in order:
        rows = groups[key]
        if not rows:
            continue
        a(f"## {title}")
        if meaning:
            a("")
            a(meaning)
        a("")
        a("| Ref | Party | Before | After | List | Matched name |")
        a("|---|---|---|---|---|---|")
        for r in sorted(rows, key=lambda x: x["ref"]):
            a("| {} | {} | {} | {} | {} | {} |".format(
                _esc(r["ref"]), _esc(r["name"]), r["before"], r["after"],
                r.get("top_list", ""), _esc(r.get("top_matched_name", ""))))
        a("")

    if groups[NEW_HIT]:
        a("---")
        a("")
        a("**A new hit is not necessarily a new designation.** It can also mean "
          "the party's name or address changed in your system, the alternate-names "
          "file loaded this time and not last time, or a threshold moved. Check "
          "the list manifest digests of both runs before concluding which.")
    return "\n".join(lines)


def open_cases_report(runs: list[tuple[str, dict[str, dict[str, str]]]]) -> str:
    """Roll every non-CLEAR case across runs into one worklist.

    A per-run report answers "what happened in this run". A compliance officer
    also needs "what is still open", which no single run can answer. Latest
    run wins per reference.
    """
    latest: dict[str, tuple[str, dict[str, str]]] = {}
    for label, rows in sorted(runs, key=lambda x: x[0]):
        for ref, row in rows.items():
            latest[ref] = (label, row)

    open_rows = [(label, r) for label, r in latest.values()
                 if r.get("disposition") != "CLEAR"]
    lines: list[str] = []
    a = lines.append
    a("# Open screening cases")
    a("")
    a(f"Every counterparty whose most recent screening was not CLEAR, across "
      f"{len(runs)} run(s). {len(open_rows)} open of {len(latest)} parties.")
    a("")
    if not open_rows:
        a("Nothing open.")
        return "\n".join(lines)
    a("| Ref | Party | Disposition | List | Matched name | Last screened in |")
    a("|---|---|---|---|---|---|")
    for label, r in sorted(open_rows,
                           key=lambda x: (DISPOSITION_ORDER.get(x[1].get("disposition", ""), 9),
                                          x[1].get("ref", ""))):
        a("| {} | {} | {} | {} | {} | {} |".format(
            _esc(r.get("ref", "")), _esc(r.get("name", "")), r.get("disposition", ""),
            r.get("top_list", ""), _esc(r.get("top_matched_name", "")), label))
    a("")
    a("Each row needs a documented human decision. Use "
      "`templates/license-determination-worksheet.md`; this table does not "
      "track whether that worksheet exists.")
    return "\n".join(lines)
