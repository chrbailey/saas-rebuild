# Rebuild plan — SYNTHETIC CRM FIXTURE → hybrid customer service system

## Decision summary

- Methodology: hybrid synthetic evidence set
- Evidence cutoff: 2026-07-31; runtime coverage is 2026-06-01 through
  2026-07-30 unless a citation says all-time
- Verdicts: KEEP 1 / SIMPLIFY 1 / DROP 1 / DEFER 1
- Target: transactional customer service + deterministic importer + assisted
  search skill
- Preservation: complete for every synthetic source category; attachments are
  explicitly not applicable
- Holdout: `search-holdout-001` is frozen and disjoint from development and
  regression groups

This plan describes the fictional tenant represented by these artifacts, not
the complete behavior of any CRM product.

## Target decisions

| Capability | Verdict | Target | Evidence | Reason |
|---|---|---|---|---|
| Customer search | KEEP | Authenticated query service; optional skill interface | `ev-search-runtime`, `ev-search-criticality` | Daily observed use supports a critical service process |
| Bulk customer import | SIMPLIFY | Versioned CSV schema + deterministic validator + idempotent job | `ev-import-runtime` | Weekly use remains; flexible mappings create repeated cleanup |
| Social enrichment | DROP | None | `ev-enrich-config`, `ev-enrich-runtime` | Disabled and never executed across complete synthetic history |
| Annual tax certificate | DEFER | Undecided | `ev-tax-window`, `ev-tax-contract` | The 60-day window excludes the annual cadence |

## Architecture

The customer record remains durable shared state behind authenticated APIs and
role-based field authorization. Imports run as idempotent jobs with template
version, row-level error output, retry, and audit events. The skill may translate
natural-language lookup requests into the narrow search contract and summarize
authorized fields; it is not the database, permission system, or import engine.

The annual certificate stays behind the source system until year-end evidence,
format obligations, sign-off, and archive requirements are observed. That DEFER
decision is a cutover blocker for the annual-tax-filing process, not permission
to omit its data.

## Dependency-derived milestones

The interaction projection reverses feature-to-entity `reads` and `writes` into
entity-contract prerequisites. It keeps capability-to-process `supports` in the
capability-to-process direction.

1. **Preservation gate** — verify all paths and digests in
   `preservation-manifest.json`.
2. **Customer contract** — define customer schema, identity policy, audit event,
   and read/write authorization.
3. **Search path** — implement authenticated lookup and run regression cases;
   then evaluate the untouched `search-holdout-001` lineage.
4. **Importer** — implement template v2 validation, idempotency key, dry run,
   row errors, and replay `import-batch-regression-001` with outbound effects
   stubbed.
5. **Parallel run** — compare search visibility and import results; any
   unregistered difference fails the milestone.
6. **Conditional cutover** — cut customer search/import only. Retain the annual
   certificate path until its DEFER revisit gate closes.

## Acceptance and rollback

Passing the four illustrative pairs proves only that the contracts and split
mechanics are executable. A real cutover requires representative, pre-frozen
holdouts across roles, error paths, imports, configuration regimes, and seasonal
behavior. Operational gates include authorization denial tests, audit delivery,
idempotent replay, backup restore, SLO monitoring, and an owner-approved rollback
window.

Rollback routes search and import traffic back to the source tenant while the
new store remains read-only. No termination notice is permitted until the
preservation manifest is complete and the annual DEFER decision has a safe
continuity plan.
