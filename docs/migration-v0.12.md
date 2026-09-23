# Migrating protocol artifacts from v0.11 to v0.12

Version 0.12 adds one optional field to model annotations, `candidates`, for
the I1 interview-to-feature matching question. Nothing it introduces is
required, so an existing v0.11 teardown needs no new content. The version bump
still needs the same careful steps as earlier releases, because two contracts
are bound to exact file bytes.

## Migrate a teardown directory

Apply these steps to your teardown directory, in order.

1. **Bump the versions.** Change every artifact `schema_version` from `0.11.0`
   to `0.12.0`: `teardown.json`, each `feature-inventory.json` entry, each
   `pairs.jsonl` line, `graph.json`, `preservation-manifest.json`,
   `success-profile.json`, `evaluation-scorecard.json`, and each line of
   `interviews.jsonl` and `model-annotations.jsonl` if you have them. Change
   only `schema_version` values; a decision record that mentions an earlier
   version is history and stays as written.
2. **Re-bind the benchmark and log it.** The version bump changes the bytes of
   `success-profile.json`, so `evaluation-scorecard.json` `benchmark.sha256` no
   longer matches. Record the approver, reason, old digest, and new digest in
   `teardown.json` `decisions`, then set `benchmark.sha256` to the new digest.
   Changing the digest without that record would silently re-lock the
   benchmark, which the protocol forbids.
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
or `preserved file digest mismatch`. `tests/test_migration_v012.py` runs this
exact procedure against a v0.11 artifact set and checks both outcomes.

## What v0.12 adds

- **`candidates` on model annotations**: the feature ids a candidate-slot
  question offered, in slot order, so `candidate-2` always resolves to the
  feature that was actually shown second. The validator requires every
  candidate to be a feature in the inventory and every answered slot to have
  been offered.
- **The `interview-matching` Jev question set (I1).** For each interview
  statement not yet linked to a feature, code picks up to five candidate
  features that share a word with the statement and sends them, sorted by
  id, with the statement text. The model picks a slot or `none`. The answer
  is only ever a suggestion: it never writes `feature_id`, which stays an
  analyst's link. A statement that shares no word with any feature is skipped
  and reported rather than sent.
- **One claim per statement.** I1 matches a statement to one feature, so
  record a statement that names several features as several statements.

The migration enables no network calls. `interview-matching` runs only when the
endpoint approves that purpose. See
`skills/saas-rebuild/references/model-perception.md`.

## Maintainers only: `scripts/migrate_v012.py`

That script bumped this repository's own schemas, corpus recipes, examples,
fixtures, and annotation writer to 0.12.0, rewriting only `schema_version`
values. It does not touch a user's teardown directory, it has already been
applied, and it refuses to run again on a tree that is no longer at 0.11.0.
The annotation `candidates` field was added by hand.
