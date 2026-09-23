# Migrating artifacts from v0.9 to v0.10

Version 0.10 adds optional, boundary-gated model perception while preserving
the deterministic teardown contract.

Run the one-time migration from the repository root:

```bash
python3 scripts/migrate_v010.py
python3 skills/saas-rebuild/tools/validate_artifacts.py <teardown-directory>
```

The migration updates schema versions, adds citation `measure` fields,
introduces `provenance.model_assist`, expands the teardown data-boundary record,
and adds the `model-io` preservation category. Review every inferred default,
especially source classifications and model endpoint approvals.

The migration does not enable network calls. To use Jev, add an approved
`model-vendor-review` preflight record and a complete System One endpoint ticket
to `teardown.json`. Keep `TYPESAFE_API_KEY` only in an ignored local `.env`.
Existing deterministic artifacts remain valid inputs after migration, and
offline behavior remains independent of the key and network.
