# Session log — the build sprint of 2026-08-07 → 2026-08-09

A condensed record of what was built, reviewed, and shipped across this
Claude Code session, for the repo's own history. Every item below is on
`main`; PR numbers are the provenance trail.

## Shipped

- **CI test suite from zero** (PR #3, merged): structure/manifest checks,
  version-sync, packaging mirror, schema fixtures, prose-to-schema
  cross-reference tests. Grew from 25 tests to 130+ across the sprint.
- **Paired training-data contract** (PR #4/#5, v0.4–v0.5): pairs.jsonl
  with four pair types (replay, judgment, perception, design), typed
  evidence citations on every verdict, process-mining and
  dependency-graph reference playbooks. Core reframe: the teardown is a
  labeling process; the replay corpus distills the legacy system against
  ground truth and doubles as the replacement's regression suite.
- **Five-agent review panel** (PR #6, v0.6.0): critic-loop gate plus four
  outside-in reviewers (cold-eyes staff engineer, SaaS-administrator
  walkthrough, expert peer referee, listing/copy accuracy). Headline
  fixes: replay preconditions, expected-divergence register,
  plane-to-class join mapping, evidence-horizon rule, verdict matrix,
  label authority on pairs, Phase 0 pre-flight, **Phase 4b preservation
  export** ("verdicts decide what gets rebuilt, never what gets saved"),
  vendor-agreement legal checklist, hardened schemas
  (additionalProperties, conditional evidence requirements), full
  outward-copy overhaul.
- **Release automation** (PRs #7/#8): release-on-version-bump — a merged
  PR that bumps plugin.json cuts its own release, gated on the suite;
  v0.6.0 released this way. (The v0.7 external overhaul later added
  reproducible builds and attestations on top.)
- **Extraction-recipe corpus** (PRs #9–#13, ongoing): schema + 100-app
  target list + per-recipe validation tests + Phase 0 wiring. 29 recipes
  researched from vendor docs (cited, dated, doc-derived-unverified) by
  a ~110-agent workflow before the session's WebSearch budget (200)
  exhausted. Remaining 71 apps: self-contained briefs in
  `docs/corpus-batches/batch-{1,2,3}.md` (PR #18) — any fresh session
  runs one with a single instruction.
- **Repo hygiene**: Dependabot label fix via a self-syncing labels
  workflow (PR #17); overview surfaces rewritten so descriptions alone
  convey the build standard (PR into #10).

## Key lessons recorded

- Background workflows only run while the session container is awake;
  overnight idle = frozen fleet. Fresh sessions with their own budgets
  beat one long session babysitting a fleet.
- Session WebSearch budget (~200) supports ~30 researched apps; the
  batch briefs are sized accordingly.
- The egress proxy blocks some vendor doc domains (e.g. Freshworks);
  agents skip honestly rather than invent.
- The owner merges fast: checkpoint small, keep every push green,
  restart the branch from main after each merge.

## Open threads

- Corpus batches 1–3 (71 apps) — briefs committed, sessions not yet run.
- Export-compliance split into its own repo — agreed in principle,
  sequenced after the corpus lands.
- v0.7.0 release — cut by bumping plugin.json once the corpus closes out.
- Community launch — see `docs/community-launch-brief.md`.
