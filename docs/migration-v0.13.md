# Migrating protocol artifacts from v0.12 to v0.13

Version 0.13 changes no existing artifact contract. It adds two optional
artifacts, `autopilot.json` and `rebuild-spec.json`, and one stricter validator
check on `DROP` verdicts. An existing v0.12 teardown needs no new content. The
version bump still needs the same careful steps as earlier releases, because
two contracts are bound to exact file bytes.

## Migrate a teardown directory

Apply these steps to your teardown directory, in order.

1. **Bump the versions.** Change every artifact `schema_version` from `0.12.0`
   to `0.13.0`: `teardown.json`, each `feature-inventory.json` entry, each
   `pairs.jsonl` line, `graph.json`, `preservation-manifest.json`,
   `success-profile.json`, `evaluation-scorecard.json`, each line of
   `interviews.jsonl` and `model-annotations.jsonl` if you have them, and
   `autopilot.json` and `rebuild-spec.json` if an autopilot run wrote them.
   Change only `schema_version` values; a decision record that mentions an
   earlier version is history and stays as written.
2. **Re-bind the benchmark and log it.** The version bump changes the bytes of
   `success-profile.json`, so `evaluation-scorecard.json` `benchmark.sha256` no
   longer matches. Record the approver, reason, old digest, and new digest in
   `teardown.json` `decisions`, then set `benchmark.sha256` to the new digest.
   Changing the digest without that record would silently re-lock the
   benchmark, which the protocol forbids. An autopilot first pass has no
   scorecard, so this step does not apply to it.
3. **Re-hash preserved files you rewrote.** Any file listed in
   `preservation-manifest.json` whose bytes changed in step 1 (usually
   `pairs.jsonl`) needs its `sha256` and `bytes` recomputed. Leave every other
   preserved file untouched; a digest that changes for any reason other than
   step 1 is a finding, not a migration step.
4. **Validate.**

   ```bash
   python3 skills/saas-rebuild/tools/validate_artifacts.py <teardown-directory>
   ```

Skipping step 2 or 3 fails validation with `benchmark digest does not match`
or `preserved file digest mismatch`. `tests/test_migration_v013.py` runs this
exact procedure against a v0.12 artifact set and checks both outcomes.

## A check that may now fail on an older teardown

The validator rejects a `DROP` verdict unless the feature has never-used
evidence and an explicitly noncritical classification. Where the feature
carries count measures, the verdict must also match what the decision matrix
derives from them. A teardown that passed under v0.12 with an unsupported
`DROP` fails with `cannot be DROP`. That is a finding to resolve by changing
the verdict or adding the evidence; it is not a migration step.

## What v0.13 adds

- **Autopilot first pass.** A hands-off mode that uses the signed-in user's own
  login and one approval. It records the signed-in role first, keeps findings
  role-scoped for non-admin accounts, makes no model calls, and writes no
  scorecard. See `skills/saas-rebuild/references/autopilot.md`.
- **A live status page.** `tools/render_status.py` renders a self-refreshing
  `status.html` from the run's JSON artifacts.
- **One portable rebuild spec per run.** `tools/build_spec.py` writes
  `rebuild-spec.json`: what to build, what not to build, what is undecided,
  history tests, and limits, copied and counted from evidence.
- **Run sheets and audits.** A HubSpot autopilot run sheet and a NetSuite usage
  audit for a signed-in browser session.
- **An optional review offer.** `offer.json` describes a paid human review. The
  status page shows it only on a finished pass and only when it has an https
  link.
- **A new default output folder**: `~/Documents/saas-rebuild/teardowns/<app>/`.

The migration enables no network calls.

## Maintainers only: `scripts/migrate_v013.py`

That script bumped this repository's own schemas, corpus recipes, examples,
fixtures, the annotation writer, and the spec builder to 0.13.0, rewriting only
version values. It does not touch a user's teardown directory, it has already
been applied, and it refuses to run again on a tree that is no longer at
0.12.0. The worked example's benchmark digest was re-bound by hand, with a
decision record, following the steps above.
