# Contributing

Contributions are welcome when they strengthen evidence quality, portability,
failure behavior, reproducibility, or the honesty of public claims.

New here? You do not need a development setup to get a feel for the project.
The [hosted browser workspace](https://saas-rebuild-workspace-christopher-baileys-projects-7c988399.vercel.app)
runs the protocol as a chat with your own Anthropic API key and nothing to
install (it has no connector into a tenant and no filesystem, so you run the
exports yourself and paste sanitized results), and its `#/corpus` view shows
every extraction recipe without a key.
The [synthetic worked example](examples/synthetic-crm/README.md) shows a
finished teardown. Most contributions below start from one of those two
places rather than from code.

## Three ways to contribute

You do not need to touch code to make this project more useful. The three
lanes, in rough order of effort:

### 1. Share a teardown report (no PR needed)

Ran a teardown — or even a partial one — on a tenant you administer, whether
in the hosted workspace or through the Claude Code plugin? File a
[Teardown Report](https://github.com/chrbailey/saas-rebuild/issues/new?template=teardown-report.yml)
issue. The form asks for structure only: verdict counts, the KEEP set,
coverage and blind spots, preservation status, and what the pipeline missed.

**Sanitize first.** No record contents, exports, customer or employee names,
real-data screenshots, or internal URLs. Ranges and categories are fine
("5–10 users", "property management suite"). If naming the app feels
uncomfortable, name only its category. The form's sanitization checkbox is a
required field, and reports that leak tenant material will be edited or
removed.

The most valuable section is usually "What this skill missed" — real gaps in
the pipeline are how the protocol improves.

### 2. Add an extraction recipe (documentation research PR)

The [extraction-recipe corpus](skills/saas-rebuild/corpus/README.md) has 29
of 100 target apps covered. Each recipe is documentary research: what the
vendor's own docs say about export rights, extraction routes, rate limits,
attachment/audit-log access, and post-termination retrieval — with a cited,
dated bibliography.

To add one:

- Pick an uncovered app from `skills/saas-rebuild/corpus/apps.json` (the
  ready-to-run research briefs in [`docs/corpus-batches/`](docs/corpus-batches/)
  cover the 71 apps without recipes and spell out the whole workflow).
- Follow the contract in
  [`skills/saas-rebuild/templates/extraction-recipe.schema.json`](skills/saas-rebuild/templates/extraction-recipe.schema.json):
  `schema_version: "0.8.0"`, unique HTTPS sources with ISO retrieval dates,
  `verification: "doc-derived-unverified"`.
- Honesty outranks completeness: never invent endpoints, nav paths, SKU
  names, or limits. `null` means "the docs don't say" — it is not a claim of
  absence.
- Put research-process caveats (a vendor page that could not be fetched, a
  limit read from a secondary source) in the structured `research_caveats`
  array, never in `export_rights.summary` or `notes`. Those fields are the
  data a reader acts on; a test rejects session or environment language in
  them.
- Before pushing, validate against the schema, update the "v0.8, N" recipe
  count in both `README.md` and the corpus README (a test pins this), and run
  `python -m pytest tests/ -q`.

### 3. Promote a recipe's verification status (evidence PR)

Every recipe starts `doc-derived-unverified`. The corpus becomes trustworthy
when people who administer real tenants confirm or correct the routes:

- `community-verified` — reviewable shared evidence (a teardown report, a
  documented walkthrough) confirms the main routes.
- `tenant-verified` — the routes were exercised end-to-end in at least one
  authorized tenant.

A promotion PR changes the `verification` field and must link the evidence
that motivated it — typically a
[Recipe Verification](https://github.com/chrbailey/saas-rebuild/issues/new?template=recipe-verification.yml)
or Teardown Report issue. Corrections
(a route that no longer exists, a limit that changed, a gated SKU) are just
as valuable as confirmations; include the same kind of evidence. One tenant
does not establish behavior across regions, SKUs, or future vendor versions,
and the recipe's notes should keep saying so.

## A good first contribution

Verify one recipe against a tenant you administer. Pick any
`doc-derived-unverified` recipe for an app you run (browse them in the
[hosted workspace's corpus view](https://saas-rebuild-workspace-christopher-baileys-projects-7c988399.vercel.app/#/corpus)
or under
[`skills/saas-rebuild/corpus/extraction-recipes/`](skills/saas-rebuild/corpus/extraction-recipes/)),
try its main export routes against your live account — UI export paths,
API endpoints, rate limits, role requirements — and PR the result:

- Routes confirmed → promotion to `community-verified` or `tenant-verified`
  with your evidence linked.
- Routes wrong or drifted → a correction with what you observed and where.
- Either way, update `last_reviewed`.

It is a bounded afternoon of work, requires no familiarity with the
codebase, and every completed verification makes day-one discovery cheaper
for the next person. You need admin (or equivalent authorized) access to the
tenant you test against — see
[Data boundary and responsible use](README.md#data-boundary-and-responsible-use).

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --requirement requirements-dev.txt
python -m pytest tests/ -q
python skills/saas-rebuild/tools/validate_artifacts.py examples/synthetic-crm
PYTHONPATH=skills/export-compliance/tools \
  python -m unittest discover \
  -s skills/export-compliance/tools/xscreen/tests \
  -t skills/export-compliance/tools
python scripts/package_skills.py --check
```

## Change rules

### Public copy

Link every strong claim to a test, benchmark, primary source, or adjacent
limitation. Update `docs/assurance-case.md` when the enforcement surface or
boundary changes.

### Schemas

- Use JSON Schema draft 2020-12.
- Set `additionalProperties: false` on contract objects.
- Add at least one valid and one invalid case for a new invariant.
- Update the synthetic example and any duplicated citation definition.
- Treat required-field or enum changes as a compatibility change.

### Skill behavior

- Keep `SKILL.md` procedural and below 500 lines.
- Put detailed techniques in one-level `references/` files.
- Add or update a fresh-session case in `evals/evals.json`. Declare any
  machine-checkable expectation in the case's `machine_checks`;
  `python skills/saas-rebuild/tools/run_evals.py` validates the spec, prints
  every case for a reviewer, and runs only those declared checks against an
  output directory (`--case N --check <dir>`). Prose expectations are graded
  by a person; the runner never grades them.
- Do not report an eval improvement without a with-skill versus prior-version
  comparison on the same cases.

### Extraction recipes

- Treat `corpus/apps.json` as a prioritized research backlog, not proof of
  adoption or implemented coverage.
- Prefer current primary vendor documentation. Identify secondary or
  community evidence explicitly in prose and do not use it to upgrade a
  verification status.
- Record an exact retrieval date, preserve explicit unknowns, and avoid
  inferring absence from documentation silence.
- Promote verification only with reviewable evidence from an authorized
  teardown; one tenant does not establish behavior across regions, SKUs, or
  future vendor versions.

### Reference implementation

For any fail-closed, legal-effect, matching, audit, or data-boundary change,
include a regression test that fails before the fix. A model error, parser
error, missing list, stale corpus, or incomplete run must never become a clean
result.

## Package

Skill versions live in `skill-versions.json`. After changing a packaged skill,
verify a fresh build without writing artifacts:

```bash
python scripts/package_skills.py --check
```

To inspect local release outputs, write them to a disposable directory:

```bash
python scripts/package_skills.py --output-dir /tmp/saas-rebuild-dist
```

The packager normalizes order, timestamps, and permissions and emits
`SHA256SUMS`. Do not commit generated archives. The release workflow builds
them from the tag, attests them, and attaches them to GitHub Releases.

## Pull request evidence

Describe:

1. the claim or invariant changed;
2. the counterexample or user case that motivated it;
3. tests/evals added;
4. compatibility and data-boundary effects;
5. any limitation that remains.
