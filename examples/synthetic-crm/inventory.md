# Surface inventory — SYNTHETIC CRM FIXTURE

Human rendering of [`feature-inventory.json`](feature-inventory.json) (the
authoritative copy) and [`graph.json`](graph.json) for teardown
`synthetic-crm-2026`. Every id, count, date, and claim below is copied from
those files; `tests/test_synthetic_markdown.py` fails if the two drift. Nothing
here is evidence from a real tenant.

Methodology: hybrid. Runtime coverage for window-bounded citations is
2026-06-01 through 2026-07-30; the evidence cutoff is 2026-07-31. The fixture
inventories four features by design, one per verdict, so there is no long tail
of skipped surfaces to log. A real inventory records what the walk skipped.

## Features (4)

| Feature | Nav path | Kind | Entities | Actions | Observed signals | Usage |
|---|---|---|---|---|---|---|
| Customer search (`customer-search`) | Customers > Search | screen | `customer` | `search`, `open-customer` | record_count 3; newest 2026-07-30; empty_state false | daily |
| Bulk customer import (`bulk-customer-import`) | Admin > Imports > Customers | form | `customer` | `validate-csv`, `import` | record_count 8; newest 2026-07-28; empty_state false | weekly |
| Social enrichment (`social-enrichment`) | Settings > Integrations > Social enrichment | integration | `customer` | `enrich` | record_count 0; empty_state true | never |
| Annual tax certificate (`annual-tax-certificate`) | Reports > Compliance > Annual tax certificate | report | `customer` | `generate-pdf` | record_count null; empty_state false; no run in the 60-day telemetry window | unknown |

Observed signals are what the walk saw on screen. They become evidence only
once a source and coverage horizon are recorded, which is what the register
below does.

## Evidence register (7 citations)

Each citation carries a stable id, an evidence class and plane, a coverage
horizon, and the conclusions it supports. `all-time` coverage is what lets the
DROP verdict in [`usage-analysis.md`](usage-analysis.md) stand;
`window-bounded` coverage is why the annual report is DEFER rather than DROP.

| Evidence id | Feature | Class / plane | Coverage | Confidence | Supports | Claim |
|---|---|---|---|---|---|---|
| `ev-search-runtime` | `customer-search` | runtime / telemetry | window-bounded, 2026-06-01 to 2026-07-30 | high | usage, verdict, dependency | Customer search was used on 38 of 60 observed days by three service roles. |
| `ev-search-criticality` | `customer-search` | human-framing / interview | point-in-time | medium | criticality, verdict, dependency | Service cannot identify an account for an inbound request without customer lookup. |
| `ev-import-runtime` | `bulk-customer-import` | runtime / transactional | window-bounded, 2026-06-01 to 2026-07-30 | high | usage, verdict, dependency | Eight customer import batches completed in the 60-day window; six required manual column cleanup. |
| `ev-enrich-config` | `social-enrichment` | structure / config-census | point-in-time | high | dependency | The enrichment connector is configured but disabled. |
| `ev-enrich-runtime` | `social-enrichment` | runtime / integration-inventory | all-time, 2024-01-01 to 2026-07-30 | high | usage, verdict | No enrichment execution exists across the complete synthetic tenant history. |
| `ev-tax-window` | `annual-tax-certificate` | runtime / telemetry | window-bounded, 2026-06-01 to 2026-07-30 | high | usage, verdict | No certificate generation was observed during a 60-day window that does not include year end. |
| `ev-tax-contract` | `annual-tax-certificate` | human-framing / contract | point-in-time | medium | criticality, verdict, dependency | The fictional operating policy requires an annual customer tax certificate. |

All seven citations are `sensitivity: public` because the fixture is invented;
a real inventory carries `internal`, `confidential`, or `restricted` citations
and the data boundary in `teardown.json` governs where they may travel.

## Graph nodes that are not features

| Node | Type | Label | Flags |
|---|---|---|---|
| `customer` | entity | Customer | — |
| `enrichment-api` | integration | Social enrichment API | edges_unverified false |
| `service-customers` | business-process | Service customers | critical process |
| `annual-tax-filing` | business-process | Annual tax filing | critical process |

## Edges (6)

| From | Type | To | Runtime status | Evidence |
|---|---|---|---|---|
| `customer-search` | reads | `customer` | observed | `ev-search-runtime` |
| `bulk-customer-import` | writes | `customer` | observed | `ev-import-runtime` |
| `social-enrichment` | exports-to | `enrichment-api` | structural-only | `ev-enrich-config` |
| `customer-search` | supports | `service-customers` | observed | `ev-search-criticality` |
| `bulk-customer-import` | supports | `service-customers` | observed | `ev-import-runtime` |
| `annual-tax-certificate` | supports | `annual-tax-filing` | unknown | `ev-tax-contract` |

The `exports-to` edge is `structural-only`: configuration proves the connector
exists, not that it ever ran. The `supports` edge for the annual certificate is
`unknown` for the mirror-image reason: the window never observed it running.
The dependency-derived milestone order that follows from these edges is in
[`REBUILD_PLAN.md`](REBUILD_PLAN.md).
