"""Consistency between SKILL.md prose, the files it references, the
schema's enums, and the issue template."""

import re

from conftest import REPO_ROOT, SKILL_DIR

# Enums whose values SKILL.md enumerates in prose and must keep matching
# the schema. `criticality` is deliberately absent: the prose defines it
# by a question ("does a business process break without it?"), not by
# listing its values.
PROSE_ENUMERATED = ["kind", "usage", "verdict", "replaceability", "unused_reason"]


def test_referenced_paths_exist(skill_md_text):
    refs = set(re.findall(r"(?:templates|references)/[A-Za-z0-9._-]+", skill_md_text))
    assert refs, "expected SKILL.md to reference templates/ and references/ files"
    missing = sorted(r for r in refs if not (SKILL_DIR / r).is_file())
    assert not missing, f"SKILL.md references files that don't exist: {missing}"


def test_prose_enums_match_schema(feature_schema, skill_md_text):
    for field in PROSE_ENUMERATED:
        values = [v for v in feature_schema["properties"][field]["enum"] if v is not None]
        missing = [v for v in values if v not in skill_md_text]
        assert not missing, f"schema {field} values not mentioned in SKILL.md: {missing}"


def test_issue_template_tracks_verdict_enum(feature_schema):
    template = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "teardown-report.yml").read_text()
    verdicts = feature_schema["properties"]["verdict"]["enum"]
    missing = [v for v in verdicts if v not in template]
    assert not missing, f"verdicts absent from teardown-report.yml: {missing}"


def test_readme_references_existing_issue_template():
    readme = (REPO_ROOT / "README.md").read_text()
    match = re.search(r"template=([A-Za-z0-9._-]+)", readme)
    assert match, "README no longer links to the issue template"
    template_path = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / match.group(1)
    assert template_path.is_file(), f"README links to missing issue template: {match.group(1)}"
