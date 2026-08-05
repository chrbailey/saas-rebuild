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
    a("**What this run does not establish.** Name screening does not detect "
      "entities blocked by the OFAC 50 Percent Rule, does not classify the "
      "item, does not resolve end-use or end-user controls that apply to "
      "unlisted parties, and does not substitute for reading the primary "
      "publication behind any hit. Machine adjudication is advisory; no case "
      "here has been cleared on model judgement alone.")
    a("")
    a("*Not legal advice. Produced by an automated screening tool for the use "
      "of the operator's compliance function.*")
    return "\n".join(lines)


def _top_score(r: ScreeningResult) -> float:
    live = [c for c in r.candidates if c.get("band") != "NONE"]
    return float(live[0].get("score", 0)) if live else 0.0
