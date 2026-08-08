---
name: saas-rebuild
description: Audit a SaaS tenant the user owns or administers, preserve its data, identify which configured capabilities are actually used, and derive a smaller replacement architecture from cited evidence. Start supported applications from cited extraction recipes, but verify every document-derived route in the tenant. Use for live-tenant or document-based teardowns, process and integration discovery, KEEP/SIMPLIFY/DROP/DEFER decisions, historical replay, and migration planning. Select the honest target for each capability—a Claude skill, deterministic code, service, application, workflow engine, or hybrid.
---

# SaaS Rebuild — evidence-driven teardown and replacement design

Systematic pipeline: inventory the tenant-specific system → identify observed
behavior and uncertainty → preserve every data category → choose the smallest
sound target architecture → verify it with disjoint historical cases.

## Guardrails (do these before anything else)

1. Confirm the user **owns or administers** the account and is analyzing their
   own tenant/data for migration purposes. Never probe other tenants, other
   users' private data, or anything the account doesn't legitimately expose.
2. **Extraction legality is a checklist, not a vibe.** Before bulk extraction,
   have the user locate these in the vendor agreement (they can search the PDF;
   no lawyer needed to *find* them): (a) the data ownership / export-rights
   clause — most agreements state customer data belongs to the customer and
   may be exported; quote it in the runbook; (b) API terms and rate limits —
   stay inside them, and prefer the vendor's bulk-export endpoints over
   hammering list APIs; (c) any anti-scraping / automated-access clause — if
   one exists, screen-scraping drops from "last resort" to "counsel signs off
   first"; (d) the post-termination data-retrieval window — record its length
   as a project deadline. Escalate to legal counsel only when: a clause
   forbids export of the customer's own data, scraping is the only route for
   something material, or the tenant contains regulated personal data
   (employee monitoring logs, health, payments) crossing a border. Everything
   through official exports and documented APIs of your own tenant, inside
   rate limits, is the normal case — do it and log it; don't stall on it.
3. Never capture credentials. The user logs in themselves in the browser; you
   drive the already-authenticated session.
4. All outputs go to `~/Dev/teardowns/<app-slug>/` (create it; ask the user for
   a different location if they prefer). Never use scratch/tmp directories.
5. **Approve the actual data boundary before acquisition.** Record whether the
   model and each connector are local, self-hosted, vendor-cloud, or mixed;
   which data classifications may cross each boundary; who approved it; and
   where artifacts are written. `raw-local-only` is an artifact-distribution
   label, not a claim that browser, connector, or model traffic stayed local.

## Phase 0 — Scope

Ask (one AskUserQuestion batch): which app, login URL, which modules matter
most, who are the users (names/roles count), and whether an admin/audit-log
area is accessible. Create the output dir and `teardown.json` state file:

```json
{"schema_version":"0.7.0","teardown_id":"example-app-2026","app":{"name":"Example App","slug":"example-app","url":null,"methodology":"live-tenant"},"started_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z","phase":0,"status":"in-progress","data_boundary":{"model_boundary":"unknown","connector_boundary":"unknown","artifact_root":"~/Dev/teardowns/example-app/","allowed_data_classes":["internal"],"approved_by":"project-owner","approved_at":"2026-01-01T00:00:00Z"},"preflight":[{"id":"authorization","status":"ready","owner":"project-owner"}],"artifacts":{"feature_inventory":"feature-inventory.json","pairs":"pairs.jsonl"},"extraction":[],"decisions":[],"action_log":[]}
```

State is resumable — on re-invocation, read `teardown.json` and continue from
the recorded phase. Each phase updates `phase` on completion. Validate every
write against `templates/teardown-state.schema.json`; a prose promise of
resumability is not a state contract.

### Phase 0 pre-flight (do these before the walk — some clocks are already running)

1. **Snapshot volatile logs today.** Login/audit/access-log retention is often
   30–90 days and every day waited is a day lost off the back of the window.
   Export whatever the admin panel offers now, crudely — refine later. Verify
   the actual retention window in the vendor's docs rather than assuming.
2. **Request the paper trail now.** Order forms, renewal quotes, and module
   line items usually live with finance/procurement and take days to surface;
   they are Phase 2's strongest stream. Ask on day one. While you're there,
   ask for the vendor agreement and note two things: the data-export/return
   clause, and the post-termination data-retrieval window — that window's end
   date is the project's hardest deadline.
3. **Check your access, and name who fills the gaps.** The pipeline wants:
   full admin UI, audit-log area (sometimes a paid SKU — file the vendor
   ticket now if missing), report builder, user/role administration, and an
   API token the user creates themselves (read-only scope, clearly named,
   revoked at project end). The user does not need to be a developer: the
   agent writes and runs the queries and profiling scripts, but planes 2/3/5
   need either an API token or a colleague who has one — record who that is
   before Phase 1b, not when you stall inside it.
4. **Approve the data boundary.** Include model, browser, connector, artifact,
   backup, and residency boundaries; block any data class the approval does not
   cover.
5. **Verify the browser-automation connector is connected** before scheduling
   a live-tenant walk. Document mode does not require one.
6. **Check the extraction-recipe corpus.** Look for
   `corpus/extraction-recipes/<app-slug>.json`; `corpus/apps.json` is a target
   index and does not imply that a recipe exists. A recipe can seed the Phase 4
   route map, the Phase 4b preservation checklist, and day-one role/SKU
   requests. It cannot prove tenant usage, entitlement, export completeness,
   or present-day vendor behavior. Re-check source freshness and confirm each
   route against the authorized tenant. Preserve the `verification` status;
   submit corrections and evidence through a reviewable recipe PR.

Record each pre-flight item's status in `teardown.json` under `preflight`;
an item marked blocked gets an owner and a ticket reference, not silence.

## Alternate mode — document-based teardown (no tenant access needed)

If the user has engagement archives instead of (or in addition to) live tenant
access — requirements, change tickets, test plans, training manuals, selection
scorecards, recovery findings, meeting notes — run Phases 1–2 against those
documents and return feature entries with precise citations. Treat change
frequency and recovery findings as candidate poor-fit signals, not truth: both
are affected by reporting practices and project scope. Label the methodology
honestly as document-based. Sanitize from the first artifact: client names
become codes, individuals become roles, and distinctive figures are generalized
only where doing so does not invalidate the evidence.

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

The replay corpus supports behavioral distillation and regression, but those
roles are not interchangeable. Before any development, assign each lineage a
`dataset_role` (`development`, `regression`, or `holdout-eval`) and stable
`split_group`. Never train, tune prompts, select architecture, or choose
thresholds using a holdout group. Never place correlated cases from one
customer, workflow instance, period, or configuration regime on both sides of
a split. Every pair carries a `sanitization_tier`; only
`sanitized-shareable` and `synthetic` artifacts may be distributed. The
`raw-local-only` label governs artifact movement only; the approved
`data_boundary` governs model and connector traffic. Each pair also records
its `label_authority`:
`system-of-record` (replay) and `observed-ui` (perception) are ground
truth; `analyst` labels (judgment, unvalidated design) are the pipeline's
own opinions — usable for behavior cloning and audit, never as eval gold.
A design pair is promoted to `validated-design` only after its workflow
passes parallel-run. Tier assignment gets its own critic check before
anything leaves the output dir: re-read every `sanitized-shareable` pair
for names, figures precise enough to identify the tenant, and internal
URLs — rounding is not anonymity when the tenant is distinctive, and the
critic that checks tiers must not be the pass that assigned them.

## Phase 1 — Feature inventory (browser walk)

Load browser-automation tools (e.g. Claude in Chrome MCP; one ToolSearch
call). Have the user log in if not already. Then walk the app breadth-first:

- Start from the main nav; enumerate every top-level item, then sub-nav,
  settings pages, report libraries, admin panels.
- For each screen: read the page text (+ screenshot for complex screens),
  record a feature entry per `templates/feature-inventory.schema.json`:
  id, nav_path, name, kind (screen | form | report | setting | integration |
  automation), business processes, data entities, actions, observed signals,
  and typed evidence. Give every citation a stable `evidence_id`, coverage
  horizon, sensitivity, support scope, and derivation parents.
- Record counts where the UI shows them ("312 records", empty-state screens,
  "last modified" columns) — this is usage evidence, capture it inline as
  `observed_signals` on the feature.
- Cap the walk sensibly: if the app has more than ~60 screens, inventory nav
  labels for the long tail and deep-walk only the modules the user named in
  Phase 0. Log what was skipped — no silent truncation.
- Write `feature-inventory.json` atomically as you go and keep its path in
  `teardown.json.artifacts` (one authoritative copy, not two drifting copies).
  Generate a human `inventory.md` rendering at the end.

## Phase 1b — Technical extraction (the five data planes)

The browser walk shows surface area; the data planes show truth. When tenant
access exists, run all five per `references/extraction-playbook.md` (full
technique matrix, platform specifics, gotchas, and the ranked default order):

1. **Configuration/metadata census** — export every custom object, field, form,
   workflow, role, saved search, enabled module (platform metadata API or SDF/
   Metadata-API export). A delta from a version-matched baseline is a candidate
   requirements inventory; runtime and human evidence determine whether it
   remains a requirement. Run first by default.
2. **Transactional archaeology** — transaction-type frequencies, volume
   time-series, human-vs-integration `created_by` attribution, row counts +
   max(modified) per table. Empty tables are absence signals only after checking
   scope, archival, retention, integration-only use, and relevant cadence.
3. **Master-data profiling** — field fill rates, cardinality, custom-field
   population %. Low fill rate is a profiling flag, not proof of abandonment;
   segment by record type, age, role, and applicable population first.
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
  citations (stable id + class + plane + claim + source + observation time +
  coverage + confidence + sensitivity + support scope + derivation) per
  `templates/feature-inventory.schema.json` — a feature with a `verdict` but
  an empty `evidence` array gets `usage: unknown` and its verdict reverted to
  DEFER until a citation exists. `workaround-external` means the job
  is actively done in a satellite tool or spreadsheet instead;
  `workaround-internal` means users bend the app from inside (status skips,
  admin-edit bypasses — surfaced by conformance checking in
  `references/process-mining.md`). Both are different, more actionable
  findings than "unused": the workaround is the requirement the configured
  flow failed to meet
- `criticality`: does a named business process break without it? Critical
  entries list stable process ids in `business_processes`.
- `replaceability`: trivial (a prompt), moderate (skill workflow), hard
  (needs external integration/state)
- `verdict`: KEEP | SIMPLIFY | DROP | DEFER, plus one-sentence **why**
- Attribute unused-ness: never-needed vs. too-complex vs. duplicate vs.
  wrong-fit vs. unknown. This drives redesign, not just deletion.

Default verdict matrix — deviations are allowed but must be recorded in
`decisions[]` with a reason: RUNTIME-evidenced use + `critical` → KEEP;
RUNTIME-evidenced use + any workaround signal → SIMPLIFY (the workaround is
the spec); `never` (all-time evidence) + not `critical` → DROP; `unknown`
usage, or window-bounded absence on a `critical` feature → DEFER pending
better evidence. Criticality follows the same citation discipline as usage:
`critical` requires a citation naming the business process that breaks
(interview, contract SLA, or a dependency-graph path to a critical process)
— an uncited `critical` is `important`.

Join rules (where Phase 1b ran): a feature is only "used" when STRUCTURE
evidence (it exists/is configured) joins with RUNTIME evidence (transactions,
telemetry, executions — see the plane-to-class mapping below). Configured-alone
resolves by evidence horizon: if the runtime evidence is *all-time* (empty
table, zero records since tenant creation), set `usage: never` with
`unused_reason: configured-never-enabled`; if the runtime evidence is
*window-bounded* (telemetry, logs) and the window is shorter than the
feature's plausible cadence, set `usage: unknown` with
`unused_reason: unknown` and note the window — "not observed in a 60-day
window" never demotes an annual feature. Score recency and criticality
separately: year-end close runs once and is still KEEP.

Plane-to-class mapping for the join rule — RUNTIME: `transactional`,
`telemetry`, `integration-inventory`; STRUCTURE: `config-census`,
`master-data`, `setup-census`, `code-analysis`; HUMAN/FRAMING: `interview`,
`contract`, `document`. `ui-walk` and `export` are *routes*, not classes:
they inherit the class of what they observed (a record count seen on-screen
or in an export is RUNTIME; a settings page seen on-screen is STRUCTURE) —
record which in the claim. HUMAN evidence corroborates a join; it never
substitutes for the RUNTIME side on its own. "Independent" means independent
*provenance*, not independent extraction route: an export of a table and a
query of the same table are one signal — when counting corroborating
citations, collapse `derived_from` chains first.

Where Phase 1b ran, write `graph.json` against
`templates/dependency-graph.schema.json` and build it per
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

## Phase 4b — Preservation export (everything, before the verdicts matter)

The extraction map serves the rebuild; this phase serves the company. Verdicts
decide what gets *rebuilt* — they must never decide what gets *saved*. The day
the subscription ends, anything not exported is gone, and retention obligations
(financial records, audit trails, e-discovery) don't care about your KEEP set.
Run this regardless of verdicts, and complete it before any termination notice
— check the contract's post-termination data-retrieval window (often 30–90
days) and treat its end date as the project's hardest deadline.

Preservation checklist — export and checksum each, or record explicitly why it
cannot be exported (vendor ticket reference, missing SKU, no route found):

- **Every entity's records** — KEEP, SIMPLIFY, DROP, and DEFER alike, full
  history where the platform offers it, not just current state.
- **Attachments, documents, and generated files** (invoices, PDFs, uploads) —
  these rarely ride along with record CSVs; find the file-export or bulk
  attachment route separately.
- **Activity history** — emails, notes, call logs, timeline events, comments.
- **The audit logs themselves** — the full available window, not the samples
  used as evidence.
- **Configuration as artifacts** — custom object/field definitions, form
  layouts, workflow/automation definitions, saved report and search
  definitions, in the platform's native export format (SDF, Metadata API
  package, config export) so they are restorable, not merely documented.
- **Users, roles, and permission assignments.**
- **Replay corpus** — for each KEEP workflow, historical transaction inputs
  AND system-of-record outputs at posting/document level (Phase 5's replay
  validation is impossible without it).

Verify completeness at export time: compare exported row counts and date
ranges against the Phase 1b tenant counts, per entity, and log the diff.
Write and validate `preservation-manifest.json` against
`templates/preservation-manifest.schema.json`: per item — route, files,
row/file counts, SHA-256 digests, gaps, and accountable gap acceptance. A
human-readable Markdown rendering is optional and must be generated from the
JSON, not maintained as a competing source of truth. Apply the approved data
boundary to the whole preservation set; require encryption, access control,
backup, and a named retention owner.

## Phase 5 — Target architecture and rebuild plan

Classify every retained capability before choosing its runtime:

| Capability property | Default target |
|---|---|
| Reasoning, analysis, document transformation | Claude skill with schemas/tools |
| Deterministic calculation or file transformation | Tested library, script, or service |
| Shared mutable state, concurrency, permissions | Application + database + identity |
| Cross-system event flow | Workflow or integration runtime |
| Regulated or irreversible action | Deterministic guard + accountable approval |

Most serious replacements are hybrid. Record each target decision and its
evidence; do not force a ledger, identity system, statutory rules engine, or
multi-user transactional workflow into prompt-only architecture.

Design the replacement:

- **Schema first**: one JSON schema per core entity (fields, confidence
  labels where extraction is fuzzy).
- **Corpus/state**: choose immutable files, a database, or an external system
  of record according to consistency, update, retention, and access needs.
- **Workflows**: each KEEP verdict becomes a target workflow; each
  SIMPLIFY gets redesigned around what users actually did, not what the app
  offered. Spreadsheet workarounds from interviews become first-class flows.
- **Bridges**: CSV in/out for whatever systems remain (accounting, ERP).
- **Audit**: append-only audit log entries for every state-changing action.
- **Out of scope honestly**: DEFER/DROP list with revisit conditions, plus
  anything needing unsupported multi-user state or external writes — choose
  an app, service, automation, controlled bridge, or the old system.

Structure the plan around a **capability map** populated from the data planes
(not interviews alone — interview-only maps reproduce the org chart), sequence
it **strangler-fig** (capability-by-capability behind the CSV/API bridges,
never big-bang), and validate by **replay**: re-run disjoint historical cases
through the replacement and diff outputs against the system of record at
posting, document, and total level. This is bounded acceptance evidence, not a
proof of universal equivalence.

Replay has preconditions — check them before trusting any diff:

- **Freeze the split before implementation.** Development, regression, and
  `holdout-eval` groups are disjoint by `split_group`. If a holdout case is
  inspected during design or debugging, demote and replace the entire lineage;
  do not pretend it remains independent.

- **The legacy system is not a pure function.** Outputs depend on
  at-the-time state (rates, balances, sequence numbers, open periods).
  Capture that state with the transaction where possible; where not,
  restrict the replay sample to transactions whose inputs are
  self-contained, and say so.
- **Historical outputs came from historical config.** If the config or
  scripts changed during the corpus window (the change log from plane 1
  tells you), partition the corpus at each change and only compare like
  with like. A diff against an output produced under a different rule set
  is noise, not a regression.
- **Replay must be side-effect-free.** Run it with every bridge stubbed or
  in dry-run mode; a replayed invoice that reaches the live accounting
  bridge is a double-posting incident, not a test. Verify the stub before
  the first batch.

Equivalence is the acceptance test **per verdict class**: KEEP workflows
must diff clean; SIMPLIFY workflows carry an **expected-divergence
register** — each intended behavior change written down *before* replay,
with the evidence that motivated it. A diff is then either (a) matches
legacy, (b) matches a registered divergence, or (c) unexplained — and only
(c) fails the milestone. An unregistered divergence discovered at replay
time is a finding, never a retroactive registry entry. Where replay shows
the legacy output was itself wrong (it happens), record it as a legacy
defect, exclude the pair from the regression suite's gold set, and do not
reproduce the bug.

Derive the milestone structure from the graph, don't guess it
(`references/dependency-graph.md`): capability islands are candidate
strangler-fig milestones, the projected dependency DAG gives their order,
load-bearing entities get their schemas first, and every articulation
point enters the risk register with an explicit bridge-or-replace
decision.

Write `REBUILD_PLAN.md` per `templates/rebuild-plan-template.md`: target
selection plus phased
milestones (walking skeleton → core workflow → bridges → parallel-run →
cutover), each milestone with a verification step.

**If the target includes a Claude skill:** package it as a versioned zip (no angle
brackets in the SKILL.md description — the workspace uploader rejects them),
upload to the org's Claude workspace, and verify the installed version
end-to-end after upload. Plan the operational envelope: corpus refresh cadence
and owner, append-only audit log location, role/permission mapping from the
old system's SoD model (mined, not copied), and a rollback path (previous zip
version retained).

## Deliverables recap

`~/Dev/teardowns/<app-slug>/`: `teardown.json`, `graph.json`, `inventory.md`,
`usage-analysis.md`, `extraction-runbook.md`,
`preservation-manifest.json`, `exports/`, `pairs.jsonl`,
`interview-questions.md` (if used), and `REBUILD_PLAN.md`. Validate every JSON
or JSONL artifact against its template before delivery. When Python and the
declared `requirements.txt` dependency are available, run
`tools/validate_artifacts.py <output-dir>` to enforce cross-file identities,
lineage isolation, graph references, and preservation digests. Summarize
KEEP/SIMPLIFY/DROP/DEFER counts, target-runtime counts, top findings, material
unknowns, holdout status, and preservation gaps.
