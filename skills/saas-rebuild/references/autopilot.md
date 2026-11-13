# Autopilot run

A hands-off first pass for one person and one login. The person logs in,
approves once, and watches a status page. Everything else in `SKILL.md` still
applies: the evidence rules, the verdict matrix, the schemas, and the rule
that verdicts never decide what gets saved. Autopilot changes the order and
removes the questions; it does not lower the evidence bar.

Use it when someone says "just run it", "autopilot", "map what I use", or
names an app and nothing else. Use the full phased run when an admin wants
contracts, interviews, API routes, replay, or a rebuild plan.

## The two stops

There are exactly two points where the run waits for the person.

1. **Login.** Open the app's login page in the browser. The person signs in
   themselves, including any MFA. Never read, type, or store a credential.
2. **One approval.** A single AskUserQuestion, asked once the app is open:

   > Anything shown on these pages is sent to the model so it can be read.
   > The run only reads and uses the app's own Export buttons. It will not
   > edit, send, delete, or buy anything. How much may it read?

   - **Everything I can see**: record contents may be read when needed.
   - **Structure and counts only**: screens, settings, totals, and dates; no
     opening of individual records.
   - **Stop.**

   Record the answer in `teardown.json` `data_boundary` and mark the
   `authorization` and `data-boundary` preflight items. Leave `vendor-terms`
   and `contracts` as `pending` and list them under `needs_you`.

   The same approval locks the first-pass benchmark below. Say so in the
   question: "This also accepts the standard first-pass goals: save
   everything, find what is used, propose nothing be removed yet."

After these two stops, ask nothing. Anything that would need a person goes
into `needs_you` in `autopilot.json`, and the run carries on with the rest.

## The first-pass benchmark (locked at the approval stop)

Phase 0b requires a locked `success-profile.json` before any usage is
inspected, so that success is not redefined around what the tenant happens
to contain. Autopilot keeps that rule without asking a second question: it
uses the fixed profile below, which is the same for every app and was
written before any tenant was seen. Write it at the approval stop with the
run's `teardown_id` and `app`, `approved_by` set to the person, and
`created_at` and `locked_at` set to the approval time.

```json
{
  "outcomes": [
    "The person knows which features of the app show evidence of use.",
    "A copy of every data class this account can export is saved locally."
  ],
  "criteria": [
    {"id": "save-reachable-data", "dimension": "data-portability", "priority": "must", "weight": 5,
     "statement": "Every data class the signed-in account can export is exported and checksummed, or recorded as a gap with a reason.",
     "acceptance": {"method": "inspection", "target": "Each preservation-manifest item is exported or carries an accountable gap.", "evidence_classes": ["structure"]}},
    {"id": "find-used-features", "dimension": "business-outcome", "priority": "must", "weight": 5,
     "statement": "Every feature found is classified as used, never used, or not yet known from cited evidence.",
     "acceptance": {"method": "inspection", "target": "No feature has a verdict without a citation; absence inside a short window is recorded as not yet known.", "evidence_classes": ["structure", "runtime"]}},
    {"id": "change-nothing", "dimension": "control", "priority": "must", "weight": 5,
     "statement": "The run changes nothing in the tenant beyond queuing the app's own exports.",
     "acceptance": {"method": "inspection", "target": "Every action_log entry is read-only, local-write, or a logged export.", "evidence_classes": ["structure"]}}
  ],
  "non_goals": [
    "Decide what the replacement must do; that needs the people who do the work.",
    "Score a replacement; there is none yet."
  ],
  "constraints": [
    {"id": "two-stops-only", "kind": "operational", "statement": "After login and one approval the run asks nothing further."}
  ]
}
```

This profile describes a first pass only. A full teardown replaces it with a
profile about the organization's own jobs and outcomes, as a numbered
revision recorded in `decisions[]` per Phase 0b. Because that later profile
is written after usage has been seen, record that fact in the same decision.

## Stop the run only for these

Set `status: blocked`, say why in `now`, render, and wait:

- the session logs out or asks for MFA again;
- the next step could only be done by writing, sending, deleting, enabling,
  connecting, or purchasing something;
- the app shows an access-denied or rate-limit page twice in a row.

## What autopilot may touch

- Reading any page the signed-in account can open.
- The app's built-in Export buttons for the account's own data. Log each one
  in `action_log`: an export queues a server-side job and may send the person
  an email, so its effect is `remote-write`, not `read-only`.
- Nothing else. No API tokens, no bulk screen-scraping of records, no
  settings changes. Routes that need those are parked in `needs_you`.

## The run directory and the status page

Create `~/Documents/saas-rebuild/teardowns/<app-slug>/` and write, before the login stop:

- `teardown.json`: phase 0, `methodology: live-tenant`;
- `autopilot.json`: per `templates/autopilot-run.schema.json`, every step
  `pending`; refresh its `updated_at` on every write;
- then run `python tools/render_status.py <run-dir>` and `open` the resulting
  `status.html` so it is on screen from the first second.

Re-run `render_status.py` after every step change and after every module of
the walk. The page refreshes itself every few seconds while the run is in
progress and stops when the `report` step is `done`. Leave `teardown.json`
at `status: in-progress`, `phase: 3`: the state schema reserves `complete`
for a finished teardown, and a first pass is not one.

Keep `now` to one plain sentence a non-technical person can follow, such as
"Reading the Workflows list (page 2 of 3)".

## Steps, in order

Use these step ids so status pages are comparable across runs.

| id | Outcome | Notes |
|---|---|---|
| `login` | An authenticated session the person created | Stop 1 |
| `approval` | A recorded data boundary | Stop 2 |
| `role` | `access_level` and `role` filled in from what the tenant shows | See below |
| `save-data` | Every export this role is allowed to run has been started | Start these early; they finish while the walk runs |
| `map` | One feature entry per screen, breadth-first | The ~60-screen cap in Phase 1 applies; log what was skipped |
| `usage` | Runtime signals attached to features as typed citations | Counts, newest/oldest dates, empty states, last-run and last-modified columns |
| `verdicts` | KEEP / SIMPLIFY / DROP / DEFER per the Phase 3 matrix | See "Verdicts without interviews" |
| `report` | Artifacts written and schema-checked; step marked `done` | Final render, then leave the page open |

A step that cannot run is `skipped` with a `detail` that says why. It is
never silently dropped, and a later run resumes from the same directory.

## Role first

The role step decides how the rest behaves. Read the account's own profile
and permission pages and record what the role can and cannot do, in the
app's own words, with the page it was read from as `source`.

- **`admin`**: the account can open user administration, billing or
  subscription pages, and account-wide exports. Findings describe the tenant.
- **`standard`**: the account edits records but cannot see administration.
- **`view-only`**: the account can read but not create, edit, or export.
- **`unknown`**: the permission page was not reachable. Infer nothing; say so.

### Standard and view-only accounts

Without admin access the run cannot see the whole tenant, so it validates the
role against its own visible history instead:

1. **Evidence is whatever this role can see**: records it owns or is
   assigned, activity timelines, its saved views and dashboards, recently
   viewed items, and counts and dates shown on list pages.
2. **Findings are role-scoped.** Begin each `why` with "For this role:".
   Never present a role-scoped count as a tenant-wide fact.
3. **Invisible is not unused.** A feature the role cannot open gets
   `usage: unknown` and `DEFER`, never `DROP`.
4. **Check the role against itself.** List what the role's name and
   permissions imply it should be doing. Anything implied but not observed
   becomes a `DEFER` plus one plain question in `needs_you`. Anything
   observed that the role would not be expected to do is a finding worth
   stating.
5. **Exports the role cannot run** become preservation-manifest gaps with the
   reason, and a `needs_you` item naming who could run them.

## Verdicts without interviews

Autopilot runs no interviews, so no feature can be cited as `critical`, and
the verdict matrix has no cell for "used but not shown to be critical". Do
not invent one. A feature with runtime-evidenced use keeps its `usage` and
gets **no verdict**; its `why` says that keep-or-simplify needs a person, and
one `needs_you` item asks which of the used features the work depends on.
The status page counts it as used either way. All other Phase 3 rules hold
unchanged; in particular a window-bounded absence is `unknown`, not `never`.

### Two traps the first live run found

- **A young account has no "all-time".** If the tenant is newer than the
  slowest plausible cadence of the feature (assume a year unless shown
  otherwise), record every count as `window-bounded` from the account's
  creation date and log one decision saying so. An empty screen in a
  week-old account is `unknown`, never `never`.
- **Vendor sample data is not use.** Records the vendor creates and labels
  as samples do not count. Record the measure as the number of non-sample
  records and say so in the claim.

## Rules own the verdicts; no model calls

Derive verdicts with the deterministic rules in `tools/rules/`, as in any
run. Autopilot does not call Jev or any other model endpoint (guardrail 6
and preflight item 7): mark `model-vendor-review` as `not-applicable` and
leave model perception to a later, reviewed run.

## What the person sees at the end

- `status.html`: the headline count ("N of M features show evidence of
  use"), then three smaller counts, verdict totals, what was saved, and the
  full feature table. The three counts are never used (needs all-time
  evidence), opened and empty so far (a screen that was read and held
  nothing, inside a window too short to call it unused; set
  `observed_signals.empty_state` to true), and not yet known. Neither of the
  last two is ever counted as unused.
- `rebuild-spec.json` and `rebuild-spec.html`, written by
  `python tools/build_spec.py <run-dir>` as the last act of the `report`
  step. The spec is the portable result: what to build (only features with a
  positive runtime measure), what not to build (DROP verdicts and all-time
  never), what is undecided, the saved data sets, and every
  system-of-record replay pair as an acceptance test. The tool copies and
  counts; it makes no judgment, and it writes the spec's limits itself.
  Never edit the spec by hand: fix the evidence and rebuild it.
- An optional review offer at the foot of a finished page, shown only when
  `offer.json` beside `SKILL.md` carries an `https://` payment link. The run
  never opens that link and sends nothing to its seller.
- The artifacts a first pass can honestly produce: `teardown.json`,
  `success-profile.json`, `feature-inventory.json`, `pairs.jsonl`
  (perception pairs from the walk), `graph.json`, and
  `preservation-manifest.json`, each validated against its own schema.
- No `evaluation-scorecard.json`: there is no replacement to score yet. An
  autopilot directory is therefore not a complete teardown, and
  `tools/validate_artifacts.py` will report the missing scorecard until a
  full run adds it. Do not write an empty scorecard to make it pass.
- `needs_you`: the short list that turns this first pass into a full run,
  such as the contract clauses, an API token, or two interview questions.

## Built to get better as models do

Each step above is stated as an outcome, not a click path. App run sheets
such as `autopilot-hubspot.md` are hints for today's models and today's
screens; when the live screen disagrees with a run sheet, the screen wins and
the difference is logged. A step a model could not complete is recorded as
`skipped` with its reason, so a more capable model can pick up the same run
directory and finish it without redoing the rest.

## Keeping it hands-off in Claude Code

Tool-permission prompts are the usual reason a run stalls. Before starting,
tell the person to grant the browser extension access to the app's site and
to allow the file and script commands for this run when first prompted.
