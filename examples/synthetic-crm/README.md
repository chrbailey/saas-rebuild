# Synthetic CRM teardown

This is what a finished teardown looks like, on a fictional CRM tenant, so
you can read every artifact the protocol produces without anyone's real data
and before pasting an API key anywhere. Start with
[`usage-analysis.md`](usage-analysis.md): four features, four verdicts, and
the evidence behind each. The same JSON and Markdown artifacts are what the
[hosted workspace](https://saas-rebuild-workspace-christopher-baileys-projects-7c988399.vercel.app)
and the Claude Code plugin emit for a tenant you administer; the preserved
export files and their digests come from exports you run yourself, since the
workspace has no connector into a tenant.

The directory is an internally consistent example of the v0.11 artifact
contracts. It is not evidence from a customer engagement, and every number in
it was invented to exercise the rules.

The example deliberately includes four different conclusions:

- a daily, critical customer-search capability to KEEP;
- a weekly bulk import to SIMPLIFY behind a deterministic validator;
- a configured enrichment integration with all-time zero executions to DROP;
- an annual tax-certificate report absent from a 60-day log window to DEFER.

It also demonstrates a hybrid target architecture, disjoint behavioral-case
roles, explicit model/connector boundaries, a typed interaction graph, and a
checksummed preservation manifest. The pre-evidence success profile is bound
to its scorecard by SHA-256; the example scores 84 across 66.67% of weighted
criteria but fails its must-have gate because weekly ingest is only partial;
annual compliance also remains unknown. CI validates both JSON Schema
conformance and cross-artifact invariants.

## Reading order

Start with the human artifacts, then open the JSON they are rendered from:

| Read | Rendered from | What it shows |
|---|---|---|
| [`evaluation-scorecard.json`](evaluation-scorecard.json) | `success-profile.json`, `feature-inventory.json` | The locked “what good looks like” criteria, evidence crosswalk, assessed coverage, weighted score, and must-have gate |
| [`usage-analysis.md`](usage-analysis.md) | `feature-inventory.json`, `teardown.json` | The KEEP / SIMPLIFY / DROP / DEFER table with a reason and evidence ids per row, and why a 60-day window cannot demote an annual report |
| [`inventory.md`](inventory.md) | `feature-inventory.json`, `graph.json` | Every feature, every citation with its coverage horizon, and the typed graph |
| [`extraction-runbook.md`](extraction-runbook.md) | `teardown.json`, `preservation-manifest.json`, the preserved files | Route and status per entity, expected fields, and the checksummed preservation record including the accepted gap |
| [`REBUILD_PLAN.md`](REBUILD_PLAN.md) | all of the above | Target selection, dependency-derived milestones, replay criteria, and cutover gates |

The rendered Markdown files are derived from the JSON, never the other way
round. `tests/test_synthetic_markdown.py` fails if a verdict, evidence id,
count, or digest in `usage-analysis.md`, `inventory.md`, or
`extraction-runbook.md` stops matching the JSON. The JSON itself is
checked by `tests/test_synthetic_example.py` and by the validator:

```bash
python skills/saas-rebuild/tools/validate_artifacts.py examples/synthetic-crm
```

## Machine artifacts

| File | Contract |
|---|---|
| `teardown.json` | `templates/teardown-state.schema.json` — run state, preflight, data boundary, extraction status, decisions, action log |
| `success-profile.json` | `templates/success-profile.schema.json` — locked outcomes, weighted criteria, acceptance methods, non-goals, and constraints |
| `evaluation-scorecard.json` | `templates/evaluation-scorecard.schema.json` — complete evidence crosswalk, score, coverage, gate, and benchmark digest |
| `feature-inventory.json` | `templates/feature-inventory.schema.json` — one entry per feature with typed evidence citations |
| `graph.json` | `templates/dependency-graph.schema.json` — feature, entity, integration, and business-process nodes with evidence-bearing edges |
| `preservation-manifest.json` | `templates/preservation-manifest.schema.json` — exported files with SHA-256 digests, record counts, and one accepted gap |
| `pairs.jsonl` | `templates/pairs.schema.json` — four behavior and judgment pairs across development, regression, and holdout-eval roles |
| `interviews.jsonl` | `templates/interviews.schema.json` — four pseudonymous interview statements from two sessions; the customer-search interview citation links the one it rests on |

Files under `exports/`, `audit/`, and `config/` contain invented data only.
Organization names use reserved `SYNTHETIC_ORG_*` tokens; there are no real
people, companies, email addresses, credentials, or tenant identifiers.
