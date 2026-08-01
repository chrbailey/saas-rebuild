# Technical Extraction Playbook

The complete evidence taxonomy for reverse-engineering what an application does
and which parts are used. Phase 1b of SKILL.md orders these; this file is the
per-technique reference. Evidence classes: **A = runtime** (what happens),
**B = structure** (what was built / what data exists), **C = human/framing**.

## The five data planes (run all five when tenant access exists)

### 1. Configuration & metadata (B — highest value per effort, run FIRST)
Census everything built on top of vanilla: custom objects, fields, forms,
workflows, roles, saved searches, enabled features/modules.
- NetSuite: SuiteQL against customization records; SuiteCloud SDF project export
- Salesforce: Metadata API (or Elements.cloud / Field Trip for field usage)
- SAP: config tables + IMG; generic SaaS: admin "customizations" screens + API schema/describe endpoints
- **The delta from vanilla IS the requirements list the client paid for.**
- Gotcha: configured ≠ used — always join to planes 2/3 and telemetry.
- Baseline diffing variant: spin up a clean trial tenant of the same
  version/edition and diff configs — catches sprawl metadata APIs miss.
  (Version mismatch = mountains of false diffs.)

### 2. Transactional data (A) — archaeology, one day of queries
- Transaction-type frequency distribution + volume time-series → alive vs dead
- `created_by` analysis: human vs integration user per transaction type — tells
  you which flows a human touches vs which are pure pipe
- Record-age histograms; last-transaction date per type
- Row-count archaeology: row counts + max(modified date) for EVERY table —
  near-zero effort, instant module-level triage (empty table = unused module)
- Gotcha: low volume ≠ low value — year-end close and tax filings are rare and
  critical. Score recency AND criticality separately.

### 3. Master data (B) — profiling script over core entities
- Field fill rates, distinct-value cardinality, custom-field population %
- 0.3%-populated custom field = abandoned experiment; document it as such
- Referential density (how connected are entities in practice)
- Gotcha: 100% populated by a default value is still meaningless — profile
  distinct values and variance, not just null rates.

### 4. Setup data (B) — operating footprint census
Org structure/subsidiaries, accounting periods and close cadence, currencies,
tax nexus, scheduled jobs, integration users/tokens, role→user assignments.
- Permission mining: join role GRANTS against login telemetry — grants wildly
  overstate use; never copy a role model without usage evidence.

### 5. Customization code (B) — static analysis, now LLM-cheap
Export all scripts/workflow definitions/formula+validation rules (SDF, Metadata
API, SE80) and have an agent summarize EVERY script into: trigger, entities
touched, business rule encoded, external calls. Each script encodes a
requirement vanilla couldn't meet — this is the richest "why" source.
- Pair with execution logs (script execution logs; SAP SCMON/UPL) to separate
  live code from dead — code shows intent, not liveness. Capture across a full
  business cycle where possible; a quarter misses annual jobs.

## Runtime evidence beyond the planes (A)

- **Usage telemetry** — login audit trails, page/report access, saved-search
  last-run dates, seat utilization. START CAPTURE DAY 1: retention windows are
  often 30–90 days. View ≠ use.
- **Integration traffic** — API/SOAP logs + iPaaS flow inventories (Celigo,
  Boomi, Workato, Mulesoft). This is the system's real external contract; the
  classic rebuild failure is breaking an integration nobody knew existed.
  Gotcha: file-drop (SFTP/CSV) and scheduled-export integrations bypass API
  logs — inventory schedulers and shared drives too.
- **Report/output inventory** — scheduled reports, generated documents,
  distribution lists. A report nobody opens is a feature you don't rebuild;
  interview the recipients of the top 20 to confirm consumption.
- **Notification/email log mining** — which alerts and approval emails actually
  fire → live workflow triggers. Dedupe by template first.
- **Process mining** — treat audit trails/status-change logs as event logs
  (case-ID + activity + timestamp; PM4Py or commercial tools) to discover
  actual process variants, rework loops, cycle times. Deploy when stakeholders
  disagree about how work really flows — case-ID correlation is engagement-
  scale effort, so it's a judgment call, not a default.
- **Task mining** (desktop capture) — the between-systems work: Excel bridges,
  swivel-chair flows. Requires agent installs + privacy sign-off; offer it,
  never assume it.

## Field-tested gotchas (learned the hard way on a live tenant)

- **"Last run / last used" columns lie in one direction.** Platform usage
  columns typically stamp UI and scheduler executions only — searches, reports,
  and queries invoked by scripts or APIs never stamp them. A blank means "no
  recorded UI execution," NOT "never used." Say it that way, or a hostile
  reviewer will dismantle the finding. Cross-check against script/API logs
  before calling anything dead.
- **The same proxy is contaminated in both directions.** Scheduled jobs stamp
  "last run" with zero human involvement (inflating "alive"); script-invoked
  artifacts never stamp (inflating "dead"). What you have is an *execution
  histogram*, not a usage histogram — label it as such.
- **Check the earliest timestamp before trusting the oldest bucket.** If no
  stamp predates a certain date despite an earlier go-live, the column may only
  populate from some enablement point; everything "older" is uninterpretable.
- **Verify retention rather than assuming it** — it can surprise in both
  directions (a platform documented as 90-day may hold years). Retention length
  changes whether telemetry is a rush job or a considered one.
- **Paginated list segments are a free histogram.** When a list paginates by
  sorted-column ranges, the segment boundary labels give you a distribution
  over that column without exporting anything. Watch the arithmetic: N/page-size
  rarely divides evenly, so report a *range*, not a point estimate, until you
  export the list.
- **Browser-driven CSV exports fail silently.** An export click may produce no
  file and no dialog, and you may not be able to check the download list from an
  automated session. Plan a manual export step; never claim exportability you
  haven't demonstrated.
- **Log every action for audit.** Every tenant-session artifact should carry an
  action log. State the read-only claim precisely: list-sort and pagination
  clicks can persist per-user view preferences, and an export click may queue a
  server-side job you cannot verify. Claim "no record/config/data changes," not
  "nothing touched the tenant."
- **Note PII you saw but didn't store.** List pages show owner and last-modified
  names. Record that they were visible and excluded, so compliance is
  documented rather than inferred.

## Validate findings adversarially before they enter the evidence base

Extraction output is a draft, not a fact. Run a critic pass over it — ideally
independent agents with distinct lenses:

1. **Data-consistency critic**: attack the arithmetic, the internal
   contradictions, and every leap from signal to conclusion. Ask "which of
   these would not survive a hostile CFO, and what one cheap check fixes it?"
2. **Process-compliance critic**: audit the session's action log against its own
   read-only rules, score each runsheet item done/partial/failed, and hunt for
   *silent* gaps — items quietly dropped rather than disclosed.
3. **Verification pass**: after applying corrections, re-check that each one
   actually landed AND that the fixes introduced no new errors. They do:
   scrubbing an identifier can leave a stale pointer claiming it lives somewhere
   it doesn't.

Expect the critics to find errors that flatter your own narrative — arithmetic
that overstates how much is unused is the characteristic failure mode of this
work. Retract in place, keep the retraction visible in the artifact.

## Human evidence (C) — multipliers on everything above

Interviews/shadowing ("show me", not questionnaires), UI crawl (per-role — one
admin crawl overstates the real UI), support-ticket/SOP/change-ticket mining
(churn concentration maps to poor fit), contracts/renewals (purchased-vs-used).

## Ranked default order (evidence value per effort, admin access assumed)

1. Config/metadata census → 2. Transaction archaeology + row counts →
3. Master-data profiling → 4. Telemetry capture (start day 1, harvest later) →
5. Integration inventory → 6. Code static analysis (LLM-summarized) →
7. Interviews to disambiguate → 8. Everything else as disputes demand.

## Rebuild-side framing (feeds Phase 5)

- **Capability map** as the scaffold: hang every piece of evidence on a
  business-capability tree. Populate it from planes 1–5, not interviews alone —
  interview-only maps reproduce the org chart, not the system.
- **Strangler-fig sequencing**: rebuild capability-by-capability behind stable
  interfaces (the CSV/API bridges), never big-bang.
- **Parallel run + replay as the validator**: re-run a sample of REAL historical
  transactions through the rebuilt skill and diff outputs against the system of
  record (posting-level, document-level, total-level). Behavioral equivalence
  on historical data is the only proof that survives a CFO.
