---
name: saas-rebuild
description: Tear down a SaaS application the user administers - log in via browser automation, inventory every screen and feature, gather used-vs-unused evidence from tenant data and user interviews, map data extraction routes, and produce a plan to rebuild the kept workflows as a Claude skill. Trigger phrases include "tear down this app", "extract and redesign", "rebuild this software as a skill", "what do we actually use in [app]", "replace [app] with a skill".
---

# SaaS Rebuild — teardown, usage analysis, and skill rebuild plan

Systematic pipeline: inventory a SaaS app's full surface area → score what is
actually used and why → map how to get the data out → design the replacement
as a Claude skill (schema + corpus + CSV bridge + audit trail).

## Guardrails (do these before anything else)

1. Confirm the user **owns or administers** the account and is analyzing their
   own tenant/data for migration purposes. Never probe other tenants, other
   users' private data, or anything the account doesn't legitimately expose.
2. Note that mass scraping may sit awkwardly with some vendors' ToS; prefer
   built-in exports, reports, and APIs over screen-scraping wherever they exist.
   Flag it to the user, don't decide for them.
3. Never capture credentials. The user logs in themselves in the browser; you
   drive the already-authenticated session.
4. All outputs go to `~/Dev/teardowns/<app-slug>/` (create it; ask the user for
   a different location if they prefer). Never use scratch/tmp directories.

## Phase 0 — Scope

Ask (one AskUserQuestion batch): which app, login URL, which modules matter
most, who are the users (names/roles count), and whether an admin/audit-log
area is accessible. Create the output dir and `teardown.json` state file:

```json
{"app": "", "url": "", "started": "", "phase": 0,
 "features": [], "evidence": {}, "extraction": [], "decisions": []}
```

State is resumable — on re-invocation, read `teardown.json` and continue from
the recorded phase. Each phase updates `phase` on completion.

## Alternate mode — document-based teardown (no tenant access needed)

If the user has engagement archives instead of (or in addition to) live tenant
access — FRDs/change tickets, test plans, training manuals, selection
scorecards, recovery-project findings, meeting notes — run Phases 1–2 against
the documents: fan out one extraction agent per evidence stream, each returning
the feature schema with cited evidence. Two hard-won rules: **change-ticket
corpora beat UI walks for mature tenants** (churn concentration maps directly
to poor-fit features), and **recovery/rescue-project findings docs are teardown
gold** (they enumerate broken and never-enabled features with CFO-level candor).
Label the report's methodology honestly as document-based. Sanitize from the
first artifact: client names become codes (keep a local-only names map),
individual names never appear (roles only), and figures are rounded.

## Paired-data capture (runs from day one)

The teardown is a labeling process — the legacy system labels replay
transactions, analysts label verdicts, the walk labels UI-to-schema
extraction — so harvest the labels as you go. Every phase appends supervised
pairs to `pairs.jsonl` in the output dir, one JSON object per line per
`templates/pairs.schema.json`. Four pair types:

- `perception` — Phase 1 walk: screen text/DOM excerpt → the structured
  feature entry it produced.
- `judgment` — Phase 3 verdicts: evidence bundle → verdict + why.
- `replay` — Phase 5 replay validation: historical transaction input → the
  system-of-record output.
- `design` — Phase 5 workflow design: usage evidence + workarounds → rebuilt
  workflow spec.

The reframe: the replay corpus makes the rebuild a **distillation of the
legacy system against ground truth** — and doubles as the permanent
regression suite for the replacement skill. Every pair carries a
`sanitization_tier`; `raw-local-only` pairs (tenant data) never leave the
output dir — only `sanitized-shareable` and `synthetic` may leave
`~/Dev/teardowns/`.

## Phase 1 — Feature inventory (browser walk)

Load browser-automation tools (e.g. Claude in Chrome MCP; one ToolSearch
call). Have the user log in if not already. Then walk the app breadth-first:

- Start from the main nav; enumerate every top-level item, then sub-nav,
  settings pages, report libraries, admin panels.
- For each screen: read the page text (+ screenshot for complex screens),
  record a feature entry per `templates/feature-inventory.schema.json`:
  id, nav_path, name, kind (screen | form | report | setting | integration |
  automation), data_entities touched, actions available, notes.
- Record counts where the UI shows them ("312 records", empty-state screens,
  "last modified" columns) — this is usage evidence, capture it inline as
  `observed_signals` on the feature.
- Cap the walk sensibly: if the app has more than ~60 screens, inventory nav
  labels for the long tail and deep-walk only the modules the user named in
  Phase 0. Log what was skipped — no silent truncation.
- Write features into `teardown.json` as you go (crash-safe), and a human
  `inventory.md` table at the end.

## Phase 1b — Technical extraction (the five data planes)

The browser walk shows surface area; the data planes show truth. When tenant
access exists, run all five per `references/extraction-playbook.md` (full
technique matrix, platform specifics, gotchas, and the ranked default order):

1. **Configuration/metadata census** — export every custom object, field, form,
   workflow, role, saved search, enabled module (platform metadata API or SDF/
   Metadata-API export). The delta from vanilla is the requirements list the
   client paid for. Run FIRST — highest evidence value per effort.
2. **Transactional archaeology** — transaction-type frequencies, volume
   time-series, human-vs-integration `created_by` attribution, row counts +
   max(modified) per table. Empty tables = unused modules in one query.
3. **Master-data profiling** — field fill rates, cardinality, custom-field
   population %. A 0.3%-populated field is an abandoned experiment.
4. **Setup census** — entities, periods, tax, scheduled jobs, integration
   tokens, role assignments (join grants to login telemetry before trusting).
5. **Code static analysis** — export all scripts/workflow definitions; fan out
   agents to summarize each into trigger + entities + business rule + external
   calls. Pair with execution logs to separate live from dead code.

Also on day 1: start telemetry capture (login/report/access logs — verify the
actual retention window rather than assuming) and inventory integrations (API
logs + iPaaS flows + file-drop/scheduled exports). Breaking an unknown
integration is the classic rebuild failure. Fold all outputs into
`teardown.json` features with `evidence` citing the plane.

Where the audit log carries a case-linkable object id, mine it as an event
log per `references/process-mining.md` — variant counts,
configured-vs-observed conformance, and median waits between activities turn
"how work really flows" from interview claims into counted evidence. It
states its own skip conditions; don't force it on thin logs.

**Every tenant session carries an action log** in its artifact, and the
read-only claim is stated precisely (sort/pagination clicks can persist view
preferences; export clicks may queue unverifiable server-side jobs). Note PII
seen on-screen but excluded from capture. Then **run the critic pass in
`references/extraction-playbook.md` before any extraction finding enters the
evidence base** — usage-column semantics and segment arithmetic produce
confident-sounding errors that reliably overstate how much is unused. Flag any
stale/unexpected integration credentials you encounter as a security finding
for the client, separate from the teardown.

## Phase 2 — Usage evidence

Four independent evidence streams; gather all four:

1. **Tenant data signals** (from Phase 1 + targeted revisits): record counts
   per module, newest/oldest record dates, empty modules, configured-but-unused
   automations, stale saved reports, user list with last-login if visible,
   audit log samples if accessible. If audit logs qualify,
   `references/process-mining.md` upgrades this stream from record counts to
   observed process behavior — its conformance findings feed
   `configured-never-enabled` and `workaround-internal`, and its bottleneck
   ranking pre-orders Phase 5 workflow priorities.
2. **Exports**: download whatever CSV/report exports the app offers for the
   core entities (guide the user through clicks if downloads need approval).
   Store under `exports/` in the output dir; summarize row counts and date
   ranges.
3. **User interviews**: AskUserQuestion batches per user group — which screens
   do you touch daily/weekly/never, what do you do OUTSIDE the app that the
   app should do (spreadsheet workarounds are gold), what do you dread, what
   would you keep if you could keep only three things. If teammates aren't in
   the room, generate `interview-questions.md` for the user to circulate and
   accept answers pasted back later (state file makes this resumable).
4. **Contracts and renewals**: order forms, renewal quotes, seat counts vs.
   assigned users, module line items. Purchased-vs-used is often the single
   strongest signal — modules bought and never enabled, seats paid and never
   assigned, upsells that quantify what the vendor thinks is missing.

## Phase 3 — Used vs. unused analysis

For every feature, score and classify:

- `usage`: daily | weekly | rare | never | workaround-external |
  workaround-internal | unknown.
  Citations are structured: each feature carries an `evidence` array of typed
  citations (plane + claim + source) per
  `templates/feature-inventory.schema.json` — a verdict without at least one
  citation is `unknown`, not a verdict. `workaround-external` means the job
  is actively done in a satellite tool or spreadsheet instead;
  `workaround-internal` means users bend the app from inside (status skips,
  admin-edit bypasses — surfaced by conformance checking in
  `references/process-mining.md`). Both are different, more actionable
  findings than "unused": the workaround is the requirement the configured
  flow failed to meet
- `criticality`: does a business process break without it?
- `replaceability`: trivial (a prompt), moderate (skill workflow), hard
  (needs external integration/state)
- `verdict`: KEEP | SIMPLIFY | DROP | DEFER, plus one-sentence **why**
- Attribute unused-ness: never-needed vs. too-complex vs. duplicate vs.
  wrong-fit vs. unknown. This drives redesign, not just deletion.

Join rules (where Phase 1b ran): a feature is only "used" when STRUCTURE
evidence (it exists/is configured) joins with RUNTIME evidence (transactions,
telemetry, executions) — configured-alone defaults to `configured-never-enabled`
until proven. Score recency and criticality separately: year-end close runs
once and is still KEEP.

Where Phase 1b ran, build the dependency graph per
`references/dependency-graph.md` before finalizing verdicts: color nodes
by verdict and act on the mismatches — a DROP node a kept path depends on
keeps its verdict but DEFERs its removal, and a KEEP island no critical
process touches gets re-challenged against the minimal-cover check.

Sanity pass: any KEEP without cited evidence, or DROP with high criticality,
gets re-checked. Write `usage-analysis.md` (verdict table + the why column)
and update `teardown.json`.

## Phase 4 — Data extraction map

For each KEEP/SIMPLIFY entity, choose the best extraction route in order of
preference: official API or an already-connected MCP connector (check
ToolSearch for one first) → built-in export → report-builder CSV →
screen-scrape (last resort, flag ToS). Produce `extraction-runbook.md`: per
entity — route, steps, expected fields, refresh cadence for the transition
period (the old app usually runs in parallel for a while).

## Phase 5 — Rebuild plan as a skill

Design the replacement:

- **Schema first**: one JSON schema per core entity (fields, confidence
  labels where extraction is fuzzy).
- **Corpus**: extracted data lives as a JSON corpus the skill loads (a single
  list file keeps the loader simple).
- **Workflows**: each KEEP verdict becomes a skill workflow section; each
  SIMPLIFY gets redesigned around what users actually did, not what the app
  offered. Spreadsheet workarounds from interviews become first-class flows.
- **Bridges**: CSV in/out for whatever systems remain (accounting, ERP).
- **Audit**: append-only audit log entries for every state-changing action.
- **Out of scope honestly**: DEFER/DROP list with revisit conditions, plus
  anything needing real multi-user state or external writes — recommend the
  right home for those (app, automation, or keep in old system).

Structure the plan around a **capability map** populated from the data planes
(not interviews alone — interview-only maps reproduce the org chart), sequence
it **strangler-fig** (capability-by-capability behind the CSV/API bridges,
never big-bang), and validate by **replay**: re-run a sample of real historical
transactions through the rebuilt skill and diff outputs against the system of
record at posting, document, and total level. Behavioral equivalence on
historical data is the acceptance test.

Derive the milestone structure from the graph, don't guess it
(`references/dependency-graph.md`): capability islands are the
strangler-fig milestones, the condensed topo-sort is their order,
load-bearing entities get their schemas first, and every articulation
point enters the risk register with an explicit bridge-or-replace
decision.

Write `REBUILD_PLAN.md` per `templates/rebuild-plan-template.md`: phased
milestones (walking skeleton → core workflow → bridges → parallel-run →
cutover), each milestone with a verification step.

**Org deployment (Claude for Work):** package as a versioned zip (no angle
brackets in the SKILL.md description — the workspace uploader rejects them),
upload to the org's Claude workspace, and verify the installed version
end-to-end after upload. Plan the operational envelope: corpus refresh cadence
and owner, append-only audit log location, role/permission mapping from the
old system's SoD model (mined, not copied), and a rollback path (previous zip
version retained).

## Deliverables recap

`~/Dev/teardowns/<app-slug>/`: teardown.json (state), inventory.md,
usage-analysis.md, extraction-runbook.md, exports/, pairs.jsonl (supervised
pairs, tiered per sanitization rule), interview-questions.md
(if used), REBUILD_PLAN.md. Send REBUILD_PLAN.md to the user at the end and
summarize KEEP/SIMPLIFY/DROP counts and the top 3 findings.
