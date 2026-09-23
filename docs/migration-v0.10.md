# Migrating protocol artifacts from v0.9 to v0.10

Version 0.10 adds optional, boundary-gated model perception while preserving
the deterministic teardown contract. Every v0.10 field it introduces is
optional, so an existing v0.9 teardown needs no new content. It does need one
careful step, because two v0.9 contracts are bound to exact file bytes.

## Migrate a teardown directory

Apply these steps to your teardown directory, in order.

1. **Bump the versions.** Change every artifact `schema_version` from `0.9.0`
   to `0.10.0`: `teardown.json`, each `feature-inventory.json` entry, each
   `pairs.jsonl` line, `graph.json`, `preservation-manifest.json`,
   `success-profile.json`, and `evaluation-scorecard.json`.
2. **Re-bind the benchmark and log it.** The version bump changes the bytes of
   `success-profile.json`, so `evaluation-scorecard.json` `benchmark.sha256` no
   longer matches. This is a benchmark revision like any other: record the
   approver, reason, old digest, and new digest in `teardown.json` `decisions`,
   then set `benchmark.sha256` to the new digest. Changing the digest without
   that record would silently re-lock the benchmark, which the protocol forbids.
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
or `preserved file digest mismatch`. `tests/test_migration_v010.py` runs this
exact procedure against a v0.9 artifact set and checks both outcomes.

## What v0.10 adds

All optional: a structured citation `measure`, `provenance.model_assist` on
pairs, `source_classes` and `model_endpoints` in the teardown data boundary, a
`model-vendor-review` preflight item, `annotation_ids` on decisions, a
`model_annotations` artifact pointer, and the `model-io` preservation category.

The migration enables no network calls. To use Jev, add an approved
`model-vendor-review` preflight record and a complete System One endpoint ticket
to `teardown.json`, and keep `TYPESAFE_API_KEY` only in an ignored local `.env`.
Offline behavior stays independent of the key and the network. See
`skills/saas-rebuild/references/model-perception.md`.

## Maintainers only: `scripts/migrate_v010.py`

That script bumped this repository's own schemas, corpus recipes, examples, and
fixtures to 0.10.0. It does not touch a user's teardown directory, it has
already been applied, and it refuses to run again on a tree that is no longer
at 0.9.0.
