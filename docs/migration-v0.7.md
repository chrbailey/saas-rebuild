# Migrating protocol artifacts from v0.6 to v0.7

Version 0.7 deliberately breaks the machine contracts. The earlier shapes
could record confident conclusions without executable provenance, reuse the
same behavioral cases for training and evaluation, and describe artifact
locality as though it were a network boundary.

Do not relabel a v0.6 file as `0.7.0`. Upgrade the semantics, then validate.

## Feature entries

Add `schema_version: "0.7.0"`. Every citation now requires:

- stable `evidence_id`;
- `evidence_class` (`structure`, `runtime`, or `human-framing`);
- acquisition `plane`, precise `source`, and `observed_at`;
- coverage horizon and confidence;
- sensitivity and the conclusion fields it `supports`;
- optional `derived_from` parents and `source_digest`.

Non-unknown usage needs a citation supporting `usage`. A verdict needs at
least one citation supporting `verdict` plus `why`. `critical` additionally
needs stable `business_processes` and criticality evidence. Review each old
conclusion; do not manufacture required metadata from memory.

## Behavioral and judgment pairs

Add `schema_version`, `pair_id`, `dataset_role`, `split_group`, expanded
provenance, and an authority compatible with `pair_type`.

Partition lineages before development:

- `development` may influence implementation or prompt/model selection;
- `regression` detects known-behavior changes but is not independent evidence;
- `holdout-eval` must remain untouched and cannot use an analyst label.

Replay pairs also need at-time configuration/state context and explicit
side-effect isolation. A `sanitized-shareable` case needs an approved,
independent sanitization-review record.

## Run state and new artifacts

Replace the informal state object with a schema-valid `teardown.json` containing
authorization/preflight state, approved model and connector boundaries,
artifact references, decisions, and an action log. Keep the authoritative
feature inventory in `feature-inventory.json` rather than duplicating it inside
state.

Add:

- `graph.json`, with business-process nodes, evidence IDs, and runtime status;
- `preservation-manifest.json`, with checksummed files and accountable gaps;
- a rebuild plan that records capability-to-runtime selection and holdout gates.

## Graph semantics

Do not reuse a v0.6 topological order. v0.7 separates observed interaction
edges from projected build prerequisites. Reconstruct the projection using the
rule table in the [dependency-graph reference](../skills/saas-rebuild/references/dependency-graph.md),
record overrides, condense SCCs, and compare observed-only with conservative
structural-edge sensitivity runs.

## Packaging and installation

The marketplace entry now uses the same-repository source `"./"`; install with
the fully qualified plugin name:

```text
/plugin install saas-rebuild@chrbailey-plugins
```

Skill versions live in `skill-versions.json`. Verify release packaging with
`python scripts/package_skills.py --check`. Archives and `SHA256SUMS` are built
from tagged source and published through GitHub Releases; generated binaries
are no longer committed.
