# Usage analysis — SYNTHETIC CRM FIXTURE

Verdicts for teardown `synthetic-crm-2026`, rendered from
[`feature-inventory.json`](feature-inventory.json), which is the authoritative
copy. Every feature id, verdict, reason, and evidence id below is copied from
that file; `tests/test_synthetic_markdown.py` fails if the two drift. Nothing
here is evidence from a real tenant.

Verdicts control what is rebuilt; they never control what is preserved. The
preservation record for the same tenant is in
[`extraction-runbook.md`](extraction-runbook.md) and
[`preservation-manifest.json`](preservation-manifest.json).

Verdict counts: KEEP 1 / SIMPLIFY 1 / DROP 1 / DEFER 1.

## Verdict table

| Feature | Verdict | Usage | Criticality | Replaceability | Why | Evidence |
|---|---|---|---|---|---|---|
| `customer-search` | KEEP | daily | critical | moderate | Observed daily lookup is required to service customers; retain the behavior behind a smaller search contract. | `ev-search-runtime`, `ev-search-criticality` |
| `bulk-customer-import` | SIMPLIFY | weekly | important | trivial | Keep weekly CSV ingestion but replace flexible mappings with a versioned template and deterministic validation. | `ev-import-runtime` |
| `social-enrichment` | DROP | never | none | trivial | The disabled connector has zero executions across the complete synthetic history and supports no identified process. | `ev-enrich-config`, `ev-enrich-runtime` |
| `annual-tax-certificate` | DEFER | unknown | critical | moderate | The short window cannot establish non-use for an annual obligation; obtain year-end evidence before selecting the target. | `ev-tax-window`, `ev-tax-contract` |

The evidence ids resolve in the evidence register of
[`inventory.md`](inventory.md), where each citation shows its class, plane,
coverage horizon, and confidence.

## How each verdict was reached

- **KEEP `customer-search`.** A runtime citation (`ev-search-runtime`,
  telemetry, window-bounded 2026-06-01 to 2026-07-30) establishes daily use; a
  separate human-framing citation (`ev-search-criticality`, interview)
  establishes that the `service-customers` process cannot run without it. The
  join of runtime and human evidence, not either alone, supports KEEP.
- **SIMPLIFY `bulk-customer-import`.** One transactional citation
  (`ev-import-runtime`) shows eight batches in the window, six of which needed
  manual column cleanup. Weekly use rules out DROP; repeated cleanup is the
  reason to replace flexible mappings rather than reproduce them.
- **DROP `social-enrichment`.** The structure citation (`ev-enrich-config`)
  shows a configured-but-disabled connector, which on its own would only prove
  configuration. The verdict rests on `ev-enrich-runtime`, whose coverage is
  `all-time` (2024-01-01 to 2026-07-30). A DROP on a `never` usage is only
  admissible with all-time runtime coverage; `unused_reason` is
  `configured-never-enabled`.
- **DEFER `annual-tax-certificate`.** `ev-tax-window` records zero runs, but
  its coverage is window-bounded and the window excludes year end, so usage is
  `unknown` rather than `never`. `ev-tax-contract` records an annual obligation
  from the fictional policy. The target decision waits for year-end evidence
  (`decision-defer-tax-report` in [`teardown.json`](teardown.json)).

## Decisions recorded in `teardown.json`

| Decision | Made at | Decision text | Reason | Evidence |
|---|---|---|---|---|
| `decision-hybrid-target` | 2026-08-01T15:00:00Z | Use a transactional service for customer state and a skill for assisted search/summarization. | Shared records require durable state and permissions; reasoning does not. | `ev-search-runtime`, `ev-search-criticality`, `ev-import-runtime` |
| `decision-defer-tax-report` | 2026-08-01T15:10:00Z | Defer target selection for the annual tax certificate. | The runtime window excludes its plausible annual cadence. | `ev-tax-window`, `ev-tax-contract` |

## What this table does not establish

- The verdicts are analyst labels. The judgment pair that records one of them
  (`pair-judgment-tax` in [`pairs.jsonl`](pairs.jsonl)) carries
  `label_authority: analyst` and `dataset_role: development`; it is usable for
  audit and behavior cloning, never as evaluation gold.
- A 60-day window with three audit events is a fixture, not a coverage claim.
  A real teardown records the actual retention window, the roles observed, and
  the surfaces that were skipped.
- KEEP and SIMPLIFY select what the rebuild must reproduce. They say nothing
  about legal compliance, export completeness, or behavioral equivalence; those
  are acceptance claims backed by the preservation manifest, the held-out
  replay lineage (`search-holdout-001`), and accountable reviewers.
