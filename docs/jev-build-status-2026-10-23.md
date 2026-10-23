# Jev local build status — 2026-10-23

The September handoff has been implemented further on `codex/jev-design-system`.
This continuation uses one agent and local tests/recorded responses only.
No additional Jev call, deployment, account setting change, or paid live
experiment was performed.

## Implemented since the handoff

- Exact replay preserves original annotation identity, effects, timestamps,
  and call-log references; repeat annotation writes deduplicate and conflicting
  ids fail. Appends are locked and flushed to disk.
- Cache keys bind responses to target, endpoint ticket, purpose, classification,
  privacy flags, and catalog. Response/annotation digests detect accidental
  corruption. Cache format changed; legacy recordings are not promoted.
- Policy evaluation uses actual calibrated probabilities and requires a pinned
  model, exact question hash, catalog version, validation reference, human
  approval, and passing canary for that model. A veto also needs a hashed twin
  question to agree. CLI operation remains shadow/prioritization/suggestion;
  no production authority policy or calibration was fabricated.
- Every set has a dedicated input shape. Features use inventory; other sets
  use classified, bounded `model-inputs.jsonl` records. Citations, edges, and
  pairs resolve to canonical artifacts. Supplemental signatures, residuals,
  and interview statements have a local target registry.
- Source classifications cannot be downgraded by public citation labels.
  PHI/EU flags reach the boundary gate. The client destination must equal the
  approved ticket. Tickets require complete approvals and control status.
- Paid CLI execution requires explicit network opt-in, a dollar cap, and a
  current price supplied by the operator. Reservations happen before calls,
  failed attempts count, and hidden request retries are disabled. Local caps
  are per run, not a provider account-wide monthly cap.
- Budget/service/replay failures preserve completed annotations and return a
  structured failure with a nonzero exit. Refusals add content-free audit events.
- Open flags and vetoes hold DROP as DEFER consistently with validation;
  human-resolved annotations do not reopen review. Missing numeric measures
  cannot create a workaround SIMPLIFY. Rationale templates cover held verdicts.
- Calibration now handles hashed lineage keys, mixed-role rejection, strict
  labels/probabilities, and equal-probability isotonic observations.
- Source migration documentation accurately distinguishes repository migration
  from an external teardown migration. The source migration includes the
  optional annotation artifact definition.

## Run and inspect

```bash
python3 scripts/demo_jev.py .jev-demo
python3 skills/saas-rebuild/tools/validate_artifacts.py .jev-demo
python3 skills/saas-rebuild/tools/jev_report.py .jev-demo
```

The demo requires a new output directory and no credential. Its fake transport
feeds the historical synthetic Jev response through the real boundary, runner,
cache, audit, annotation, replay, and review paths. The summary distinguishes
simulated calls and historical fixture tokens from actual network usage ($0).
It writes `.jev-demo/jev-review.json`; canonical example files stay unchanged.

## Remaining acceptance gates

Local verification on this build: `747 passed in 8.34s`; the canonical synthetic
teardown and generated demo both validate (`4 features, 4 pairs`); both skill
packages pass reproducibility/source-parity/checksum checks; Git whitespace
checks pass. The executed demo reports zero network calls, zero cost, a valid
audit chain, exact replay, and unchanged source evidence.

- Independent review has not been completed. No additional agents were used.
- M1's 500-state, three-repeat agreement and billing-semantics experiments,
  frozen live canary, and provider overload observation still need an expressly
  budgeted future run. The manual workflow is opt-in with a price supplied by
  its operator; it remains a single-call contract spike.
- M2–M6 rollout requires retrospective engagements, appropriate human/SoR gold,
  calibration validation, blind-first review, and measured reviewer time/error
  savings. These are data/acceptance prerequisites rather than claims a local
  software build can establish.
- No provider monthly account cap is configured by this software; the original
  $5 constraint must include any account usage outside this command too.
- A future frontend may consume sidecars, but the current browser app has no
  Jev network path or Jev key handling.

See [the protocol and input format](../skills/saas-rebuild/references/model-perception.md)
for operational details.
