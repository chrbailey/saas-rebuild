# Extraction runbook — SYNTHETIC CRM FIXTURE

Per-entity extraction record for teardown `synthetic-crm-2026`, rendered from
the `extraction` array of [`teardown.json`](teardown.json), the artifact list
of [`preservation-manifest.json`](preservation-manifest.json), and the
headers of the preserved files themselves. Every route, status, count, byte
size, and digest below is copied from those files;
`tests/test_synthetic_markdown.py` fails if the two drift. Nothing here is a
route into a real product.

The runbook serves two readers. The rebuild needs the KEEP and SIMPLIFY
entities on a repeatable route for the parallel-run period. The company needs
every data class preserved, checksummed, or recorded as an accepted gap, before
any termination notice, regardless of verdict.

## Extraction map

| Entity | Route | Status | Notes |
|---|---|---|---|
| `customer` | built-in-export | verified | Synthetic CSV count matched three-record source census. |
| `audit-event` | api | verified | Synthetic 60-day window. |
| `attachment` | none | verified | Synthetic tenant declares no attachments. |

Route vocabulary follows `templates/teardown-state.schema.json`: `api`,
`connector`, `built-in-export`, `report-csv`, `scrape`, or `none`. `verified`
means the route was exercised and its output reconciled against a source
census; `planned` and `blocked` are the other two states.

## Per-entity detail

### `customer`

- Route: built-in CSV export (`exports/customers.csv`).
- Expected fields: `customer_id`, `name`, `status`.
- Reconciliation: 3 exported rows against a three-record source census.
- Consumers: `customer-search` (KEEP, reads) and `bulk-customer-import`
  (SIMPLIFY, writes), per the `reads`/`writes` edges in `graph.json`. Both
  remain on the source tenant during parallel run, so the transition-period
  refresh must at least precede each weekly import batch; the synthetic
  artifacts do not fix a cadence, and a real runbook states one.
- Replay: the `import-batch-regression-001` lineage in `pairs.jsonl` replays a
  template-version-2 import against `config/workflows.json#imports` with
  `side_effect_free_verified: true`.

### `audit-event`

- Route: API export (`audit/events.csv`).
- Expected fields: `event_id`, `case_id`, `actor_role`, `action`, `timestamp`.
- Coverage: 2026-06-01 through 2026-07-30 (3 rows in the fixture).
- Use: the source for `ev-search-runtime` and `ev-tax-window`. The full
  available window is preserved, not only the sample used as evidence.

### `attachment`

- Route: none. The fictional tenant has no attachment subsystem.
- Recorded as a `not-applicable` preservation artifact with an accepted gap,
  not omitted. In a real tenant an attachment class with no route is a
  `blocked` row with an owner and a vendor ticket.

## Preservation status

Digests are SHA-256 over the file bytes as committed; the validator
(`skills/saas-rebuild/tools/validate_artifacts.py`) recomputes them and
rejects the directory on any mismatch.

| Artifact | Category | Status | Route | File | Bytes | SHA-256 | Records |
|---|---|---|---|---|---|---|---|
| `customer-records` | entity-records | exported | built-in CSV export | `exports/customers.csv` | 119 | `533f0b590d0978143d042d969a94fbbf87b34593aa957cb7584ccfc1617e611e` | 3 |
| `audit-events` | audit-log | exported | API export | `audit/events.csv` | 233 | `3e2b34227cb969c6a8e317ed37608663a06d212ab797c92b0861de2b18de7743` | 3 |
| `workflow-configuration` | configuration | exported | metadata API | `config/workflows.json` | 218 | `2bda19bf246c2e45816a22ff68778f0eca7cfaf91cb2a2f0ec74bbf8a65a7e8f` | null |
| `behavioral-cases` | replay-corpus | exported | local JSONL generation | `pairs.jsonl` | 3641 | `5606f21065216b760ac213f19375373c7a10bd810049e41a7fe32b442896ea13` | 4 |
| `attachments` | attachments | not-applicable | No attachment subsystem exists in this example | — | — | — | gap: The fictional source contains no attachment feature or records. |

`record_count: null` for the configuration artifact means the manifest does
not count records for it, not that it is empty. The attachments gap was
accepted by `synthetic-example-owner` at 2026-08-01T16:44:00Z with no ticket,
which is only acceptable because the gap is a declared property of the
fixture.

## What this runbook does not establish

- That any of these routes exists in a real CRM. The fixture's routes are
  labels, not vendor documentation; a real runbook cites the recipe or vendor
  page for each route and records the role, SKU, and rate limit it needed.
- That the export is complete. Reconciliation against a source census is the
  check; here the census is three invented records.
- Vendor terms. `preflight.vendor-terms` in `teardown.json` is
  `not-applicable` for the fixture; a real teardown quotes the export-rights
  clause and the post-termination retrieval window.
