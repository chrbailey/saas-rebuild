# Handoff: SaaS Rebuild + Jev/System One

## Stop condition and budget warning

The user reported that this session exhausted their available Codex/agent
credits. Do **not** spawn subagents, browse, or make another live Jev call
without fresh, explicit authorization. Continue with local repository work
only.

The agent team was attempted twice. Every independent agent failed with the
account usage-limit error and produced no review. Do not claim that an
independent critic pass happened.

Only one real TypeSafe/Jev API request was made. It used synthetic/public data
and returned 925 input tokens and 301 output tokens. At the public price used
by the guard ($0.042 per million input tokens, output free), its estimated Jev
cost was $0.00003885. The Codex/agent-credit exhaustion is separate from that
Jev API usage.

## Repository state

- Repository: `https://github.com/chrbailey/saas-rebuild.git`
- Working directory: `/Users/christopherbailey/Documents/ChatGPT/SaaS-Rebuild`
- Branch: `codex/jev-design-system`
- Base/tracking point: `origin/main`
- The local `.env` contains `TYPESAFE_API_KEY`, is mode `0600`, and is ignored.
  Never print, stage, commit, copy, or include it in logs.
- `.env.example` contains only a placeholder.
- The source plan remains at:
  `/Users/christopherbailey/Library/Group Containers/group.com.apple.coreservices.useractivityd/shared-pasteboard/items/D4420560-0204-4A58-8577-3FFDAC8492BB/saas-rebuild-jev-plan.md`

## What is implemented

### M0 deterministic and contract layer

- Protocol version bumped from `0.9.0` to `0.10.0` across schemas, 29 recipes,
  examples, fixtures, manifests, documentation, and generated web data.
- One-time repository migration script: `scripts/migrate_v010.py`.
- Deterministic rules under `skills/saas-rebuild/tools/rules/`:
  structured measure derivation, evidence horizon, liveness, runtime edge
  status, verdict matrix, rationale templates, and raise-only combination.
- Zero-third-party System One adapter under
  `skills/saas-rebuild/tools/systemone/`:
  exact endpoint/auth wire format, Choice/Score/Noul parsing, bounded retry,
  endpoint boundary tickets, state minimization, secret/host/date/digit
  scrubbing, budget/rate limits, content-addressed cache, replay, calibration
  helpers, SPRT, canary comparison, synthetic benches, and fakes.
- `systemone/audit.py` is byte-identical to the hardened xscreen audit module.
- CLI: `skills/saas-rebuild/tools/jev_run.py`, with
  `offline|shadow|live|replay`, local `.env` key loading, hard call/token/cost
  guards, content-free refusal logs, and append-only annotations.
- Question catalogs for features, citations, graph edges, process mining,
  sanitization, replay residuals, and interviews.
- New annotation and internal catalog/call-log/calibration schemas.
- Boundary/schema additions for endpoint approvals, source classes, ZDR, BAA,
  transfer mechanism, structured citation measures, model assistance, and
  `model-io` preservation.
- Validator invariants for endpoint/target resolution, data-class bounds,
  citation sensitivity, open veto/flag vs. `DROP`, sanitization rejection,
  annotation references, and model-assisted holdout exclusion.
- Browser v1 makes no Jev calls. The static web data only documents the
  server-side/CLI feature.
- Manual live workflow is opt-in only:
  `.github/workflows/jev-contract.yml`. Normal CI makes no Jev calls.

### Documentation and tests

- Protocol: `skills/saas-rebuild/references/model-perception.md`
- Migration notes: `docs/migration-v0.10.md`
- Live evidence: `docs/jev-contract-spike-2026-09-22.md`
- Pinned synthetic response fixture:
  `tests/fixtures/systemone/jev-1.13.0-feature-perception.json`
- New tests cover wire shape, answer parsing, retries, boundary refusal,
  minimization, 10,000 seeded raise-only cases, cache/replay, audit tampering,
  calibration refusal, SPRT, catalog validation, stdlib-only imports, offline
  byte equivalence, annotation invariants, and exact shared-audit parity.
- Four new skill eval cases cover undeclared endpoints, PHI without a BAA,
  model-caused `DROP`, and veto explanation.

## Verification completed

Before the final small redaction-regex, pinned-fixture, and handoff edits:

- Full repository suite: `723 passed in 7.56s`.
- Worked synthetic teardown validator: passed (`4 features, 4 pairs`).
- Package parity/checksums: passed for both archives.
- Focused Jev + annotation tests: `23 passed`.
- Git whitespace check: clean.
- Audit implementation byte comparison: exact.

The next LLM must rerun the local suite because the last few changes were made
after that full run. These commands are local and make no network/Jev calls:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python skills/saas-rebuild/tools/validate_artifacts.py examples/synthetic-crm
.venv/bin/python scripts/package_skills.py --check
git diff --check
```

## Live contract spike completed

One shadow request evaluated all F1–F8 questions in one call against the
synthetic `customer-search` feature:

- model returned: `jev-1.13.0`
- input/output tokens: `925 / 301`
- client-observed latency: `163 ms`
- parsed annotations: `8`
- request-id header: absent
- shadow effects: `none`
- call-log head:
  `c116ac44a98824f7f4f0ca2a2d3c81905f4e5c2df3c2902d2c97d63096fbf0ef`
- replay: one cache hit, zero calls, zero tokens
- validator after replay: passed

The temporary live artifacts were at
`/var/folders/2z/cbnn_6m912q1975b3435d4km0000gn/T/tmp.Ulm9vr6elf/synthetic-crm`
and may be removed by the OS. The safe response fixture and measured summary
are committed in the repository; the key is not.

## Known gaps and review findings still required

Treat the branch as an M0 implementation with a bounded M1 contract spike,
not as completed M1–M6 production adoption.

1. Rerun the full local tests after the final edits listed above.
2. Perform an independent code/security review; prior critic agents failed
   before reviewing anything.
3. Review replay semantics. A replay run currently creates a new run id and
   appends new annotations. Because replay is neither `shadow` nor `live`,
   suggestions can retain `suggest` and uncalibrated high-authority effects
   become `prioritize`. Decide whether replay must reproduce the original
   annotation effects exactly or intentionally recompute them.
4. Threshold application is scaffolded but incomplete: `Runner._effect`
   checks whether a threshold exists, but it does not yet calibrate the answer
   or compare a probability with the threshold. Keep live high-authority
   behavior disabled until this is implemented and tested.
5. `jev_run.py --set` loads every catalog but currently constructs feature
   state and targets only. Add set-specific readers/targets before claiming
   citation, edge, process, sanitization, replay-residual, or interview runs.
6. Validator target resolution supports feature, citation, graph-edge, and
   pair targets. Event signatures, replay residuals, and interview statements
   intentionally fail closed until their registries/artifacts are defined.
7. The optional workflow runs a single synthetic shadow call; it does not yet
   run a frozen canary or a full live bench.
8. M1 acceptance gates are not complete: no 500-state three-repeat agreement
   run, no billing comparison between one vs. many questions, no frozen canary,
   and no 429 live observation. Do not spend more API or Codex credits on
   these without explicit approval.
9. M2–M6 require real retrospective engagements, human/SoR gold, blind-first
   review, and reviewer-minute measurement. None were performed. No accuracy,
   savings, or production-readiness claim is justified.
10. Review `docs/migration-v0.10.md` and `scripts/migrate_v010.py` together.
    The script migrates this repository source tree, not an arbitrary external
    teardown directory; make that distinction explicit or add a safe artifact
    migration mode.
11. Consider adding `model_annotations` to the migration script's teardown
    artifact properties. The schema was patched manually after the scripted
    migration.
12. Validate the revised call-log schema against both `jev.call` and
    `jev.gate.refused` entries in tests. The live call path is validated; the
    refusal event schema deserves a direct test.
13. Decide whether a generated `model-annotations.jsonl` must already be
    declared in `teardown.json.artifacts`. The current validator accepts the
    conventional filename even when the optional state pointer is absent.

## Recommended takeover sequence

1. Read this handoff, the attached plan, and
   `skills/saas-rebuild/references/model-perception.md`.
2. Confirm `.env` remains ignored and do not display its contents.
3. Run only the four local verification commands above.
4. Inspect `git status`, `git diff --check`, and the branch history.
5. Fix test or documentation failures locally.
6. Review the 13 known gaps in order, keeping all live calls disabled.
7. Only after explicit user authorization, decide whether any remaining M1
   live experiment is worth the account/credit cost.

## Non-negotiable safety contract

- Jev is perception/veto/routing only; it never owns recorded decisions.
- Code reads numbers and dates; Jev receives minimized text.
- Model authority is raise-only. It may add review or turn `DROP` into
  `DEFER`; it may never cause `DROP`, approval, clearance, edge removal, or
  replay equivalence.
- Every call needs a complete endpoint ticket and allowed data classes.
- Restricted data requires ZDR, PHI requires a BAA, and EU personal data
  requires a transfer mechanism.
- Offline mode must remain byte-identical and make no network call or artifact
  write.
- Never send the local API key to a browser or commit it to Git.
