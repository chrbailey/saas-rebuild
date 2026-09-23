# Migrating protocol artifacts from v0.10 to v0.11

Version 0.11 adds an optional interview-statement artifact,
`interviews.jsonl`. Nothing it introduces is required, so an existing v0.10
teardown needs no new content. The version bump still needs the same careful
steps as v0.10, because two contracts are bound to exact file bytes.

## Migrate a teardown directory

Apply these steps to your teardown directory, in order.

1. **Bump the versions.** Change every artifact `schema_version` from `0.10.0`
   to `0.11.0`: `teardown.json`, each `feature-inventory.json` entry, each
   `pairs.jsonl` line, `graph.json`, `preservation-manifest.json`,
   `success-profile.json`, `evaluation-scorecard.json`, and each
   `model-annotations.jsonl` line if you have one.
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
or `preserved file digest mismatch`. `tests/test_migration_v011.py` runs this
exact procedure against a v0.10 artifact set and checks both outcomes.

## What v0.11 adds

- **`interviews.jsonl`** (template `templates/interviews.schema.json`), one
  statement per line: a pseudonymous respondent with role and user group,
  the session and channel it came from, recorded consent scopes, a topic
  (`usage`, `workaround`, `pain`, `keep`, `other`), the text, and whether it
  is verbatim. A verbatim quote must be `confidential` or `restricted`. Only
  an analyst links a statement to a feature (`feature_id` with
  `linked_by: "analyst"`).
- **`statement_ids` on citations.** Once `interviews.jsonl` exists, every
  citation with plane `interview` must list the statements it rests on, and
  be at least as sensitive as the most sensitive of them. Without the file,
  interview citations are validated exactly as in v0.10.
- **An optional `artifacts.interviews` pointer** in `teardown.json`. The
  validator reads `interviews.jsonl` whenever it exists; a pointer naming any
  other file fails.
- **Validator checks.** Unique statement ids, feature links that resolve,
  statement sensitivity inside the approved boundary, and no email addresses
  or phone numbers in statement text. Annotations with target kind
  `interview-statement` now resolve against statement ids, and an open
  model flag or veto on a statement linked to a `DROP` feature fails
  validation, as one on the feature itself does.

Interview statements stay HUMAN/FRAMING evidence. They corroborate a join and
never set `usage` or cause a decision on their own.

The migration enables no network calls. The `interviews` Jev question set
reads only `usage` statements that an analyst linked to a feature and whose
respondent consented to `model-perception`, sends only the statement text,
and runs only when the endpoint approves the `interviews` purpose. See
`skills/saas-rebuild/references/model-perception.md`.

## Maintainers only: `scripts/migrate_v011.py`

That script bumped this repository's own schemas, corpus recipes, examples,
fixtures, and annotation writer to 0.11.0, and added the citation and
teardown fields above. It does not touch a user's teardown directory, it has
already been applied, and it refuses to run again on a tree that is no longer
at 0.10.0. `templates/interviews.schema.json` was written by hand.
