# Migrating artifacts from v0.9 to v0.10

Version 0.10 adds optional, boundary-gated model perception while preserving
the deterministic teardown contract.

For maintainers rebuilding the repository's canonical schemas and fixtures,
the one-time source migration is:

```bash
python3 scripts/migrate_v010.py
```

This script edits this repository; it does not migrate an arbitrary engagement
directory. It adds optional schema definitions, not measured values or vendor
approvals. Do not run it against existing engagement material by changing its
root constant. On an external v0.9 teardown, preserve a backup, update each
artifact's schema_version, and refresh any preservation bytes/digests and the
scorecard benchmark digest affected by that serialization change. New fields
are optional: add citation measures only from known source observations, never
from model guesses. Then validate the migrated engagement:

```bash
python3 skills/saas-rebuild/tools/validate_artifacts.py <teardown-directory>
```

The protocol adds citation `measure` definitions, `provenance.model_assist`,
the endpoint data-boundary contract, and the `model-io` preservation category.
Review source classifications and model endpoint approvals explicitly.

The migration does not enable network calls. To use Jev, add an approved
`model-vendor-review` preflight record and a complete System One endpoint ticket
to `teardown.json`. Keep `TYPESAFE_API_KEY` only in an ignored local `.env`.
Existing deterministic artifacts remain valid inputs after migration, and
offline behavior remains independent of the key and network.
