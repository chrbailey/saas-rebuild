# Synthetic CRM teardown

This directory is a fictional, internally consistent example of the v0.7
artifact contracts. It is not evidence from a customer engagement.

The example deliberately includes four different conclusions:

- a daily, critical customer-search capability to KEEP;
- a weekly bulk import to SIMPLIFY behind a deterministic validator;
- a configured enrichment integration with all-time zero executions to DROP;
- an annual tax-certificate report absent from a 60-day log window to DEFER.

It also demonstrates a hybrid target architecture, disjoint behavioral-case
roles, explicit model/connector boundaries, a typed interaction graph, and a
checksummed preservation manifest. CI validates both JSON Schema conformance
and cross-artifact invariants.

## Reading order

Start with the human artifacts, then open the JSON they are rendered from:

| Read | Rendered from | What it shows |
|---|---|---|
| [`usage-analysis.md`](usage-analysis.md) | `feature-inventory.json`, `teardown.json` | The KEEP / SIMPLIFY / DROP / DEFER table with a reason and evidence ids per row, and why a 60-day window cannot demote an annual report |
| [`inventory.md`](inventory.md) | `feature-inventory.json`, `graph.json` | Every feature, every citation with its coverage horizon, and the typed graph |
| [`extraction-runbook.md`](extraction-runbook.md) | `teardown.json`, `preservation-manifest.json`, the preserved files | Route and status per entity, expected fields, and the checksummed preservation record including the accepted gap |
| [`REBUILD_PLAN.md`](REBUILD_PLAN.md) | all of the above | Target selection, dependency-derived milestones, replay criteria, and cutover gates |

The three rendered Markdown files are derived from the JSON, never the other
way round. `tests/test_synthetic_markdown.py` fails if a verdict, evidence id,
count, or digest in the Markdown stops matching the JSON. The JSON itself is
checked by `tests/test_synthetic_example.py` and by the validator:

```bash
python skills/saas-rebuild/tools/validate_artifacts.py examples/synthetic-crm
```

## Machine artifacts

| File | Contract |
|---|---|
| `teardown.json` | `templates/teardown-state.schema.json` — run state, preflight, data boundary, extraction status, decisions, action log |
| `feature-inventory.json` | `templates/feature-inventory.schema.json` — one entry per feature with typed evidence citations |
| `graph.json` | `templates/dependency-graph.schema.json` — feature, entity, integration, and business-process nodes with evidence-bearing edges |
| `preservation-manifest.json` | `templates/preservation-manifest.schema.json` — exported files with SHA-256 digests, record counts, and one accepted gap |
| `pairs.jsonl` | `templates/pairs.schema.json` — four behavior and judgment pairs across development, regression, and holdout-eval roles |

Files under `exports/`, `audit/`, and `config/` contain invented data only.
Organization names use reserved `SYNTHETIC_ORG_*` tokens; there are no real
people, companies, email addresses, credentials, or tenant identifiers.
