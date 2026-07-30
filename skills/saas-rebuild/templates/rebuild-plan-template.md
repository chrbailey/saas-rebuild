# Rebuild Plan — {APP} → Claude skill

## Executive summary
What the app does today, what fraction is actually used ({KEEP}/{TOTAL} features),
what the replacement skill covers, and what stays out of scope.

## What we keep and why
| Workflow | Today (app) | Tomorrow (skill) | Evidence it matters |
|---|---|---|---|

## What we drop and why
| Feature | Verdict | Why (never-needed / too-complex / duplicate / wrong-fit) |
|---|---|---|

## Skill architecture
- Entities and schemas (one JSON schema per core entity)
- Corpus: extraction source, refresh cadence, single-list-file loader
- Workflows (one section per KEEP/SIMPLIFY verdict)
- CSV bridges to remaining systems
- Audit log design
- Confidence labeling for fuzzy-extracted fields

## Data migration
Per entity: extraction route, field mapping, validation check (row counts,
spot-check N records), transition refresh plan while both systems run.

## Milestones
1. **Walking skeleton** — schema + loader + one end-to-end workflow. Verify: ...
2. **Core workflows** — all KEEP flows. Verify: parallel-run against the app on N real cases.
3. **Bridges + audit** — CSV in/out, audit trail. Verify: round-trip a record.
4. **Parallel run** — both systems live for {N} weeks; discrepancy log reviewed weekly.
5. **Cutover** — old app to read-only; exit criteria: ...

## Risks and open questions
- Multi-user/state needs the skill cannot cover, and where they should live instead
- ToS / data-residency notes
- DEFER list with revisit conditions
