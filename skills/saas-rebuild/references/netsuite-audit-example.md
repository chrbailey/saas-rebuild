# Example: NetSuite order-to-cash usage

Fictional single-subsidiary assessment. The period is January 1 through December
31, 2025. Three of four scoped surfaces were inspected. Integration delivery
history was inaccessible to the observed role.

| Capability | Configuration and runtime | Why it matters | Verdict |
| --- | --- | --- | --- |
| Sales orders | Active form. 480 distinct headers in the window, matching a separate total. E1 | Staff release orders to fulfillment. Owner confirmed the handoff. E4 | KEEP the behavior |
| Manual route field | Active header field. Populated on 18 of 480 eligible orders. E2 | The field handles delivery exceptions. Confirmed by the process owner. E4 | SIMPLIFY into an exception-only input |
| Annual credit exception workflow | Active deployment. Zero observed runs in 30 days of retained logs. E3 | Full-year usage and downstream effects are unresolved | DEFER |
| Carrier integration | Active configuration. No permitted access to delivery logs | Runtime and downstream dependency are unknown | DEFER |

## Evidence register

| ID | Evidence | Reproduction and coverage |
| --- | --- | --- |
| E1 | Aggregate transaction search and independent order report | Same subsidiary, dates, and statuses. Count distinct headers. 480 in both sources |
| E2 | Aggregate field population search | Same eligible headers as E1. 18 nonblank, 462 blank. Header field only |
| E3 | Workflow history | 30 days retained. No broader window verified |
| E4 | Owner interview | Confirmed fulfillment handoff and manual routing exceptions. Does not prove runtime volume |

## Internal pilot

Pilot an internal exception queue with operations and supervisor roles. Keep
sales-order posting and the ledger in NetSuite. Use a reviewed batch handoff
with a unique source order reference and a rejected-row report. Replay held-out
ordinary orders and routing exceptions, reconcile every accepted and rejected
order to the source list, and test the supervisor approval and rollback to the
existing form. Retain the source data and existing controls during the pilot.
