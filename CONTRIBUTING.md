# Contributing

Contributions are welcome when they strengthen evidence quality, portability,
failure behavior, reproducibility, or the honesty of public claims.

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
- Add or update a fresh-session case in `evals/evals.json`.
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
