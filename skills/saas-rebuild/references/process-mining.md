# Process Mining on Audit Logs

Upgrades the pipeline's weakest evidence (interviews: "which screens do
you touch") to its strongest: observed behavior. A mined audit log shows
what the process actually is — variants, rework loops, waits — with case
counts attached. Evidence class A (runtime). The extraction playbook
calls this a judgment call; the judgment is the first section below.

## When it applies — and when to skip

Minimum viable log: every event carries **actor + timestamp + action +
a case-linkable object id** (order id, ticket id, invoice id — something
that groups events into one unit of work). Status-change histories,
approval logs, and workflow execution logs all qualify. Page-view
telemetry does NOT — no case id, no process.

Bail out honestly when:

- **Retention under ~60 days.** You'll see fragments of cases, not
  cases. Fall back to the SQL directly-follows query over transactional
  tables (created/modified dates per document chain), or don't claim
  process evidence at all. Never present a fragment window as "the
  process."
- **No case-linkable object id**, and none derivable by joining the log
  to a transaction table. Same fallback. An actor+timestamp log without
  a case notion is telemetry, not an event log.
- **Stakeholders already agree how work flows and the flow is simple.**
  Case correlation and cleanup cost real hours; spend them where planes
  1–3 left a dispute or a mystery.

Where it does apply, it is the one evidence stream that survives "that's
not how we actually do it" — because it IS how they actually do it.

## Event-log construction (the genuinely hard part)

Discovery algorithms are commodity. The log you feed them is where
teardowns go wrong.

**Case notion first.** The case is the unit of work whose lifecycle you
care about: order-to-cash → the order id; ticket flows → the ticket id;
procure-to-pay → the PO id. The wrong case notion produces confident
nonsense: mine order-to-cash with customer_id as the case and every
customer's orders interleave into one mega-trace — the miner reports
"Invoice Paid followed by Order Created" loops that look like massive
rework and are actually just the next order. The graph renders fine; nothing
errors; the findings are garbage. If one case spawns children (one order,
many invoices), pick the level the business names when asking "where is
it?" — and record the choice in the artifact.

**Activity naming.** Audit logs record UI events (field X changed, field
Y changed, record viewed); processes are made of business activities.
Collapse before mining: all field edits on a record within one session →
one "Order edited"; status transitions keep their target status as the
activity name ("Approved", "Shipped"). Rule of thumb: an activity is
something a process owner would put in a swimlane; a healthy process has
5–15 distinct activities. If you're seeing 30+, you're mining UI noise —
collapse harder. If the median trace is 1–2 events, see the critic
section: your case notion is wrong.

**Timestamp gotchas, all field-observed:**

- Mixed timezones: UI-written rows in server-local time, API-written rows
  in UTC. Negative durations between consecutive events are the tell —
  check for them before anything else, then normalize to UTC.
- Bulk-import backfill: at go-live, thousands of cases "created" in the
  same minute. Exclude cases starting before go-live plus a buffer, or
  your variant and duration stats describe the migration script.
- Integration actors flood the log: one service account can emit 90% of
  events. **Segment by created_by into human and integration lanes
  before mining, and mine them separately** — the human lane shows the
  work, the integration lane shows the pipes, and blending them shows
  neither. (Reuse the plane-2 created_by attribution.)

## Discovery

Start with the **directly-follows graph (DFG)**: per case, sort events by
timestamp; count every consecutive activity pair across all cases. It's a
GROUP BY — works everywhere, no libraries — and answers most teardown
questions (dominant path, rework edges, dead branches) on its own. Draw
it with edge counts; edges with tiny counts relative to case volume are
the exceptions worth interrogating.

If Python is available on-prem, `pip install pm4py` gets you the
inductive miner and proper visualizations. It's a heavy dependency
(graphviz, pandas); don't install it to answer questions the DFG already
answers. Minimal working snippet:

```python
import pandas as pd, pm4py

df = pd.read_csv("events.csv")  # cols: case_id, activity, ts
df["ts"] = pd.to_datetime(df["ts"], utc=True)
log = pm4py.format_dataframe(df, case_id="case_id",
                             activity_key="activity",
                             timestamp_key="ts")
dfg, starts, ends = pm4py.discover_dfg(log)
pm4py.save_vis_dfg(dfg, starts, ends, "dfg.png")
# only if the DFG leaves structural questions:
net, im, fm = pm4py.discover_petri_net_inductive(log)
pm4py.save_vis_petri_net(net, im, fm, "model.png")
```

## The three teardown-relevant analyses

### 1. Variant analysis → SIMPLIFY evidence

A variant is a distinct activity sequence; count cases per variant, then
compute top-k coverage. Heuristic: **if the top 5 variants cover under
~60% of cases in a process the org calls "standard," that is quantified
proof the app doesn't fit the work** — a SIMPLIFY candidate with a number
attached, and the strongest single line you can put in usage-analysis.md.
Caveat: high variant counts are also produced by too-fine activity naming
(re-check granularity) and by genuinely project-shaped work where every
case legitimately differs. One interview question ("should these all
follow the same path?") settles it before the finding ships.

### 2. Conformance → configured vs. lived

Replay observed traces against the configured workflow (the approval
chains and status machines from the plane-1 config census; PM4Py fitness
checking, or by hand for small state machines). Two asymmetric findings:

- **Configured transitions never traversed** = unused branches. Feeds
  `configured-never-enabled` in Phase 3, now at transition granularity
  instead of feature granularity — you can DROP a branch of a KEEP
  workflow.
- **Observed paths the configuration doesn't define** — status skips,
  reopen-and-edit loops, approval bypasses via admin edit. This is
  `workaround-internal`, the in-app sibling of `workaround-external`:
  users bending the tool from inside instead of fleeing to a
  spreadsheet. Like its sibling it **feeds the Phase 5 redesign, not
  deletion** — the workaround IS the requirement the configured flow
  failed to meet.

### 3. Bottlenecks → Phase 5 automation ranking

For each directly-follows edge, compute the **median** waiting time
between the two activities (median, not mean — a few stuck cases dominate
the mean). Rank edges by median wait times case count. The longest waits
are what the rebuilt skill should automate first: that is where work sits
in queues, and it turns Phase 5 workflow prioritization from opinion into
a ranked list with hours attached.

## SQL fallback (no PM4Py, no Python)

Directly-follows counts straight off the event table:

```sql
WITH ordered AS (
  SELECT case_id, activity, ts,
         LEAD(activity) OVER (
           PARTITION BY case_id ORDER BY ts) AS next_activity
  FROM events)
SELECT activity, next_activity, COUNT(*) AS n
FROM ordered WHERE next_activity IS NOT NULL
GROUP BY activity, next_activity ORDER BY n DESC;
```

Add `LEAD(ts) ... - ts` in the CTE and take percentile_cont(0.5) per edge
for the bottleneck table from the same query. If the platform's query
layer lacks window functions, export the sorted log and compute pairs in
pandas or a spreadsheet — the classic triangular self-join (b after a
with a NOT EXISTS between them) is quadratic and breaks on timestamp
ties. Ties are common (bulk updates stamp identical times): break them
with a secondary sort on event id or the pair counts wobble between runs.

## Emitting evidence into teardown.json

Every finding enters `teardown.json` as a typed citation, same shape as
the other planes: plane `telemetry` for audit/event-log findings,
`transactional` for the SQL-fallback-over-document-tables variant; a
one-sentence claim; and the source — the exact query or log window plus
case count, so the finding is re-runnable. Example:

```json
{"plane": "telemetry", "claim": "Top-5 variants cover 41% of 2,310
  human-lane orders in the 90-day window; standard flow claim fails.",
 "source": "audit_log 2026-05-01..2026-07-30, human lane, DFG query v2"}
```

**No finding enters the evidence base without passing the critic pass in
the extraction playbook** — plus the mining-specific checks below.

## Critic checks specific to process mining

Run before the playbook's general critics; each has killed a finding in
practice.

- **Retention sampling bias.** A 60-day window over-represents short
  cases: long-running cases are truncated at both ends and either vanish
  or appear artificially short. Count only cases that both start AND end
  inside the window, report the exclusion rate, and say the window out
  loud in the claim.
- **Survivor bias.** Mining completed cases only hides abandonment — and
  abandoned cases are themselves a finding (where do cases die?). Mine
  open and abandoned cases as their own lane; the activity where cases
  stall is frequently the same edge the bottleneck analysis flags.
- **Case-notion sanity check.** Median trace length of 1–2 events means
  the case notion is wrong (events aren't correlating), NOT that the
  processes are trivial. Fix the join before publishing anything.
- **Seasonality.** A quarter of logs misses year-end close, annual true-
  ups, renewals. A path absent from the window is "not observed in the
  window," never "dead" — cross-check every absence claim against the
  Phase 3 recency/criticality split rule before it can demote a feature.
