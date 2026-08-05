---
name: export-compliance
description: Run U.S. export-control restricted-party screening on premise against the official government lists (CSL, OFAC SDN and Non-SDN, BIS Denied Persons, Entity, Unverified and Military End User, State DDTC debarred). Deterministic extraction and name matching, model-assisted adjudication of candidate hits, an independent critic pass, and a hash-chained audit trail sized for the five-year retention rules. Trigger phrases include "screen this customer list", "denied party screening", "are we allowed to ship to this company", "restricted party check", "OFAC screening", "export compliance", "replace our screening SaaS".
---

# Export Compliance — restricted party screening, on premise

Screen counterparties against the official U.S. denied and restricted party
lists, decide what a hit actually means for a specific shipment, and leave a
record that survives an audit five years later.

Built for three readers at once: a small business that needs a defensible
answer today, a legal team that needs the basis for it, and a company pulling
this function back in-house from a screening SaaS.

## The division of labour (read this before changing anything)

**Extraction and matching are deterministic. Analysis is not. Nothing is
cleared by a model alone.**

| Stage | Who does it | Why |
|---|---|---|
| Fetch and parse the lists | Code | Provenance must be a hash, not a recollection |
| Name matching and scoring | Code | The same input must produce the same result in 2031 |
| Legal effect of a hit | Code (rule table) | The consequence of an SDN hit is not a judgement call |
| Is this the same party | Model | Needs context a string metric cannot read |
| Was that judgement sound | Independent critic model | The maker cannot check the maker |
| What to do about it | Human | Strict liability; a person signs |

The matcher is tuned for **recall, not precision**. The two errors are not
symmetric: an extra row for an analyst to read costs ten minutes, a missed hit
costs an unlicensed export under a strict-liability penalty regime. Never tune
the floor upward to reduce review volume without evidence.

## Guardrails (do these before anything else)

1. **This is not legal advice, and the skill says so in every artifact.** It
   produces screening evidence and a structured analysis. A licensing decision
   is made by the operator, on advice of counsel.
2. **Never clear a party on model judgement.** A CLEAR disposition is only
   reachable when the deterministic matcher found nothing above the review
   floor. Code enforces this; do not route around it.
3. **Confirm every hit against the primary publication.** The Consolidated
   Screening List is the operational source; it is not the legal source of
   record. Entity List scope, Non-SDN program directives and denial-order
   dates all have to be read at the source.
4. **Counterparty data is confidential.** Default to a local model backend. If
   a hosted model is used, say so explicitly and record it in the run summary —
   the operator may have contractual or regulatory limits on sending customer
   names to a third party.
5. **Never invent a legal conclusion for an unrecognized list.** An unmapped
   source escalates. Silence is not a clear.

## The tool

`tools/xscreen/` is a zero-dependency Python 3.11+ package. Standard library
only, no network calls outside `refresh`, so it installs and runs inside a
closed network.

```
python3 -m xscreen.cli --home ~/Dev/export-compliance refresh
python3 -m xscreen.cli --home ~/Dev/export-compliance status
python3 -m xscreen.cli --home ~/Dev/export-compliance screen parties.csv
python3 -m xscreen.cli --home ~/Dev/export-compliance explain "Acme Trading Ltd"
python3 -m xscreen.cli --home ~/Dev/export-compliance audit verify
python3 -m xscreen.cli --home ~/Dev/export-compliance selftest
```

Exit codes make it usable as a shipping gate: `0` clean, `1` infrastructure or
usage error, `2` cases need human review, `3` at least one BLOCKED disposition.

Run `selftest` first on any new install. It is the evidence that the engine on
this machine behaves as documented.

## Phase 0 — Scope

Ask in one AskUserQuestion batch: what is being screened (customer master,
vendor master, a single transaction, a whole book of business), what systems
hold the counterparty data, whether the items are ITAR or EAR (or unknown),
whether there is an existing screening tool being replaced, and who signs off
on a hit. Create `~/Dev/export-compliance/` and record the answers in
`scope.json`.

If the operator has an existing screening SaaS, get a sample of its output.
Parallel-running the two and diffing the dispositions is the strongest
possible acceptance test, and it is the same replay-validation move that
`saas-rebuild` uses for any system replacement.

## Phase 1 — Acquire the lists (deterministic)

`xscreen refresh` downloads and parses the sources in
`tools/xscreen/sources.py` and writes `lists/manifest.json` recording, per
file: the URL that actually worked, HTTP status, fetch timestamp, byte count,
SHA-256, parsed row count, and any columns the parser did not recognize.

Defaults are CSL plus the OFAC primaries. **Load `SDN_ALT` whenever you load
`SDN`.** OFAC publishes most transliteration variants in the alternate-names
file, not the primary record; screening primary names alone is a known,
quantifiable false-negative rate that you have chosen to accept.

Hard rules:

- **Stale lists are a false clear.** Screening refuses to run on a snapshot
  older than seven days. `--allow-stale` exists for deliberate historical
  re-screening and records the override in the audit log.
- **A degraded refresh is not a successful refresh.** If a source fails to
  download, the manifest says so and the run is marked degraded. Never present
  a partial list load as a complete screen.
- **Unrecognized columns are reported, not dropped.** Government files change
  shape without notice; a new `alt_names_2` column must surface as a warning,
  not vanish.

If the environment blocks government hosts (many corporate networks and
sandboxes do), that is a network policy finding to report, not something to
work around. Download on a permitted machine and move the files in — `refresh
--offline` parses a directory of cached files and still produces a full
manifest with hashes.

## Phase 2 — Extract the parties to screen (deterministic)

Get the counterparty list out of the operator's systems by the most structured
route available, in order of preference: a database query or API → a built-in
export → a report CSV → parsing documents. This is the `saas-rebuild`
extraction ladder and the ranking is the same for the same reason: each step
down loses fidelity and gains failure modes.

What to pull, per party: reference id, name, every alias/DBA/former name the
system holds, address, country, and the role in the transaction (customer,
end user, consignee, intermediate consignee, freight forwarder, bank).

Then the transaction context, which drives the rules engine rather than the
matcher: ultimate destination, ECCN or EAR99 determination, item description,
stated end use.

Two extraction rules that cost people real money when skipped:

- **Screen every party to the transaction, not just the one you invoice.**
  Freight forwarders, intermediate consignees, end users and banks are all
  separately screenable, and the end user is the one the end-use controls
  attach to.
- **Aliases are not optional.** A customer master that stores "trading as"
  names in a notes field is holding your recall in a free-text column. Mine it.

The party file is a CSV; column names are matched by alias set (see
`templates/party-file.schema.json`). Unmapped columns are reported.

## Phase 3 — Deterministic screening

`xscreen screen` runs matching and the rules engine with no model involved.
Output per party: candidates with band (EXACT / STRONG / WEAK / NONE), score,
the signals behind the score, and rule flags with citations.

Read `references/matching-methodology.md` before tuning anything. The short
version of what the matcher handles: corporate-form equivalence (LLC/Ltd/
GmbH/OAO/JSC), diacritics and punctuation, token reordering ("Surname, Given"
vs "Given Surname"), transliteration drift via a consonant skeleton, dropped
name parts (a missing patronymic), initialisms, and shortened trade names.

Three deliberate behaviours that look like bugs and are not:

- **A country mismatch never demotes a band.** Listed addresses are sparse and
  frequently historical. Geography is recorded as a signal for the adjudicator;
  it is never allowed to clear a name hit by itself.
- **Names under four characters match only exactly.** Fuzzy-matching two-letter
  strings buries real hits in noise.
- **Blocking truncation is disclosed on the candidate.** When a query's tokens
  are so common that the search was bounded, every candidate carries
  `blocking_truncated_tokens`. No silent truncation.

## Phase 4 — Model adjudication of candidates (advisory)

Only candidates the matcher surfaced are adjudicated, and only for one
question: **is this the same real-world party?** Not "may we ship" — identity
only. The model receives the counterparty, the listed party, and the matcher's
signals, and returns a structured verdict with discriminating evidence.

Guardrails enforced in code, not in the prompt:

- The candidate set is closed. Verdicts for ids that were not in the set are
  discarded; candidates the model skipped become UNCERTAIN.
- A model verdict of DIFFERENT_PARTY against an EXACT name match does not
  clear it. It is recorded as a recommendation with a guardrail override, and
  the case still requires a human.
- Any transport failure, unparseable response or schema violation produces
  UNCERTAIN plus escalation. **An error is never a pass.**
- Free text from the counterparty record and the listed-party remarks is
  wrapped as untrusted data and the model is told not to follow instructions
  found inside it. A company can name itself anything it likes.

Backends are pluggable (`--backend`): a local OpenAI-compatible server for
on-premise operation, or a hosted API. With no backend configured the pipeline
still completes and routes every candidate to a human.

## Phase 5 — Critic loop (independent validation)

Every adjudicated case goes to a second model that never saw the adjudicator's
prompt, only the evidence and the conclusions. Its brief is adversarial and
asymmetric: assume there is an error, and hunt hardest for **the candidate
that was dismissed too easily**.

Ralph routes on the critic's verdict — commit, retry with a targeted brief, or
escalate after three attempts. A critical finding blocks a commit regardless of
risk score. Each retry gets a *fresh* adjudication so the worker cannot defend
its previous answer.

**Use a different model family for the critic** (`--critic-backend`). Two
samples from one model share failure modes; two families do not, and the
disagreements are precisely the cases worth a human's time. The tool warns when
adjudicator and critic are the same model.

See `references/adjudication-playbook.md` for the critic lenses and the
failure modes worth targeting.

## Phase 6 — Disposition, report, audit

Dispositions: CLEAR, REVIEW, CONFIRMED_HIT, BLOCKED, ESCALATE. The
deterministic layer sets a floor; adjudication may raise it and may never lower
it. A case with any candidate above the review floor can never end as CLEAR.

Outputs land in `runs/<timestamp>/`: `REPORT.md` (worklist, case detail,
provenance, limitations), `dispositions.csv`, `results.jsonl`, `summary.json`.

The audit log is append-only and hash-chained: each entry carries the SHA-256
of the previous one, so editing history invalidates every hash after it and
deleting an entry breaks the sequence. This is tamper-*evident*, not
tamper-proof — a person with write access can recompute the chain. Publish the
daily head hash somewhere the operator cannot rewrite (`xscreen audit head`);
that is what converts it into real evidence.

Retention is five years (EAR 762.6; OFAC 501.601). `xscreen audit verify`
prints the retention floor alongside the chain status.

**Every report states what the run does not establish**, and the list is not
boilerplate — each item is a real gap that name screening cannot close:

- **The OFAC 50 Percent Rule.** Entities owned 50% or more, directly or
  indirectly, in the aggregate, by blocked persons are themselves blocked and
  **do not appear on any list**. Name screening cannot find them. Beneficial
  ownership is a separate diligence step.
- **Classification.** Whether a licence is required depends on the item's
  ECCN, which screening does not determine.
- **End-use and end-user controls on unlisted parties.** 15 CFR 744.21 applies
  to military end users whether or not they are on the MEU List.
- **Entity List scope.** The licence requirement is scoped to the items named
  in the entry, and footnote designations can trigger a Foreign Direct Product
  Rule. Read the entry.

## Phase 7 — Ongoing screening

Screening once is a snapshot; the lists change weekly. Set up:

- **Re-screen on list change.** `refresh` then `screen` the whole book of
  business; diff `dispositions.csv` against the prior run. New hits on existing
  customers are the entire point — a party you cleared in March can be
  designated in April.
- **Screen at transaction time**, not only at onboarding. Destination and end
  use change per shipment even when the customer does not.
- **Re-screen when the counterparty changes**: new address, new ownership, new
  ultimate consignee.

Wire it to a schedule and keep the audit log continuous across runs.

## Replacing a screening SaaS

`references/deployment-onprem.md` covers the full path. The sequence that
works, borrowed wholesale from `saas-rebuild`'s strangler-fig approach:

1. Install and `selftest`. Refresh the lists. Verify counts against the
   published list sizes.
2. **Parallel run.** Screen the same book through both systems and diff. Every
   discrepancy is a finding about one of them: investigate before assuming the
   incumbent is right or that it is wrong.
3. Tune only on evidence from the diff, and only in the recall-preserving
   direction. Record every threshold change with its justification.
4. Cut over when the diff is understood, not when it is empty — it will not be
   empty, because the two tools draw the fuzzy-match line differently.
5. Keep the old system read-only for the retention period, or export its
   history first.

The commercial value of the incumbent is usually the workflow, the case
management and the "somebody else attested to this", not the matching. Be
honest with the operator about which of those you are and are not replacing.

## Deliverables recap

`~/Dev/export-compliance/`: `scope.json`, `lists/` (raw snapshots, manifest,
parsed corpus), `runs/<timestamp>/` (REPORT.md, dispositions.csv,
results.jsonl, summary.json), `audit/screening-audit.jsonl`. Send REPORT.md to
the user, lead with the BLOCKED and ESCALATE counts, and state plainly which
obligations the run did not discharge.
