# Rebuild plan — {APP} → {TARGET SUMMARY}

## Decision summary

- Methodology: {live-tenant | document-based | hybrid}
- Evidence cutoff and coverage: {timestamp, windows, known blind spots}
- Verdicts: {KEEP}/{SIMPLIFY}/{DROP}/{DEFER}
- Target shape: {skill | code | service | app | workflow | hybrid}
- Preservation status: {complete | gaps accepted | blocked}
- Holdout status: {frozen groups, contamination incidents, replacements}
- Decision owner and date: {owner, timestamp}

State the narrowest defensible conclusion. Distinguish observed tenant behavior
from vendor-product behavior and unknown behavior from absence.

## Scope and data boundary

| Boundary | Approved mode | Allowed data | Owner | Evidence/reference |
|---|---|---|---|---|
| Model | | | | |
| Browser/connector | | | | |
| Artifact store/backup | | | | |
| Replacement runtime | | | | |

List authorization, contractual/export constraints, residency, retrieval
deadline, and exclusions. `raw-local-only` describes artifact distribution; it
does not establish a local model or connector path.

## Evidence quality and uncertainty

| Claim | Evidence IDs | Horizon | Confidence | Counterevidence / limitation |
|---|---|---|---|---|

Record sampling, retention, role coverage, archival, seasonality, case-notion,
and undocumented-integration risks. Collapse `derived_from` lineages before
counting corroboration.

## Capability decisions

| Capability / process | Verdict | Target runtime | Evidence IDs | Why | Revisit trigger |
|---|---|---|---|---|---|

Target-runtime gate:

- reasoning/document work → skill with schemas/tools;
- deterministic transform → tested code or service;
- shared mutable state/concurrency/permissions → app, database, identity;
- cross-system event flow → workflow or integration runtime;
- regulated/irreversible action → deterministic guard and accountable approval.

Explain each exception. Do not force a transactional system into a prompt-only
target.

## Target architecture and contracts

- Core entity/event schemas and versioning policy
- Systems of record and consistency boundaries
- Reasoning/tool layer, if any
- Deterministic rules and tests
- Identity, roles, segregation of duties, approval controls
- Integration contracts, idempotency, retries, and dead-letter handling
- Audit, retention, observability, incident response, backup, and restore
- Expected-divergence register for every intended SIMPLIFY change

## Dependency-derived migration design

Reference `graph.json` and its algorithm version.

| Milestone | Projected prerequisites | Components | Boundary bridges | Sensitivity to unknown edges |
|---|---|---|---|---|

Explain interaction-to-dependency projection overrides, SCCs, articulation/cut
risks, unverified integration boundaries, and critical-process coverage. A
disconnected discovered graph is not proof of independence.

## Data migration and preservation

| Entity/artifact | Route | Mapping/version | Count/range check | Digest | Gap owner |
|---|---|---|---|---|---|

Reference `preservation-manifest.json`. Preserve all verdict classes,
attachments, activity, audit history, configuration, identity/permission
assignments, and replay material before any termination notice. Define restore
tests rather than assuming a successful export is usable.

## Verification design

| Acceptance level | Dataset role | Split boundary | Oracle | Pass rule |
|---|---|---|---|---|
| Component | development/regression | | | |
| Workflow | regression | | | |
| Parallel run | holdout-eval | | | |
| Cutover | holdout-eval + operational SLOs | | | |

Freeze `split_group` assignments before implementation. Capture legacy config
and relevant state, stub every side effect, and compare only like configuration
regimes. Classify each diff as equivalent, pre-registered intended divergence,
legacy defect, or unexplained failure. Passing finite cases is bounded evidence,
not proof of universal equivalence.

## Milestones and gates

1. **Preservation gate** — required artifacts exported, checksummed, restore-
   sampled, gaps accepted.
2. **Walking skeleton** — one end-to-end target path; contracts and telemetry
   verified.
3. **Core capability milestones** — ordered by projected prerequisites, each
   with regression, boundary, and rollback checks.
4. **Parallel run** — both systems process frozen holdouts; discrepancies are
   adjudicated without rewriting the expected-divergence register.
5. **Cutover** — SLOs, controls, ownership, support, recovery, and exit criteria
   pass; old system becomes read-only or is terminated only after preservation.

## Risk, rollback, and open questions

| Risk / unknown | Likelihood | Impact | Detection | Mitigation | Owner | Deadline |
|---|---|---|---|---|---|---|

Include DEFER revisit conditions, hidden-state replay risk, data-quality risk,
unknown integrations, vendor retrieval deadlines, privacy/security constraints,
operating ownership, and rollback duration.
