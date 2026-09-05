# Migrating protocol artifacts from v0.8 to v0.9

Version 0.9 adds an explicit, pre-evidence definition of success and a
machine-checked scorecard. Existing v0.8 teardown artifacts are not complete
v0.9 teardowns until the two new files below exist and pass cross-file checks.

## Lock the benchmark

Create `success-profile.json` from the decision owner's stated outcomes,
non-goals, and constraints. Each criterion needs a unique stable id, a
must/should/could priority, a 1–5 weight, and a falsifiable acceptance method,
target, and required evidence classes. Record approval and `locked_at`. Do not
backfill a benchmark from the final verdicts without labeling that limitation;
doing so loses the protection against hindsight bias.

## Build the crosswalk

Create `evaluation-scorecard.json` with exactly one entry for every locked
criterion. Bind it to the exact `success-profile.json` bytes using SHA-256.
Every scored entry cites evidence ids from `feature-inventory.json` and covers
the evidence classes its criterion requires. Unknown criteria have a null score
and remain visible in assessed coverage.

The validator recomputes total and assessed weight, coverage, weighted score,
must-have gaps, unknown criteria, and gate status. It rejects duplicated or
missing criteria, unknown evidence ids, a stale benchmark digest, missing
evidence classes, or hand-edited summary arithmetic.

## Update state and versions

Add `success_profile` and `evaluation_scorecard` to
`teardown.json.artifacts`. A teardown with `status: complete` must name both.
After the new contracts validate, update all SaaS Rebuild artifact
`schema_version` values from `0.8.0` to `0.9.0`.
