"""Consistency between SKILL.md prose, the files it references, the
schema's enums, and the issue template."""

import re

import yaml

from conftest import REPO_ROOT, SKILL_DIR

# Fields whose values SKILL.md enumerates as a "a | b | c" list. These are
# parsed out of the prose and compared to the schema as sets, both
# directions, so a value added or removed on either side fails.
PIPE_ENUMERATED = {
    "kind": r"kind \(([a-z]+(?: \| [a-z]+)+)\)",
    "usage": r"`usage`: ([a-z-]+(?: \| [a-z-]+)+)",
    "verdict": r"`verdict`: ([A-Z]+(?: \| [A-Z]+)+)",
}

# Fields whose values the prose mentions individually rather than as one
# list; checked schema-to-prose only, with word boundaries so e.g. "hard"
# cannot be satisfied by "hard-won". `criticality` is deliberately absent:
# the prose defines it by a question, not by listing its values.
WORD_PRESENT = ["replaceability", "unused_reason"]


def schema_values(feature_schema, field):
    return {v for v in feature_schema["properties"][field]["enum"] if v is not None}


def test_referenced_paths_exist(skill_md_text):
    refs = set(re.findall(r"(?:templates|references)/[A-Za-z0-9._-]+", skill_md_text))
    assert refs, "expected SKILL.md to reference templates/ and references/ files"
    missing = sorted(r for r in refs if not (SKILL_DIR / r).is_file())
    assert not missing, f"SKILL.md references files that don't exist: {missing}"


def test_pipe_enumerations_match_schema_exactly(feature_schema, skill_md_text):
    # Collapse the line wrapping so enumerations that span lines parse.
    text = re.sub(r"\s+", " ", skill_md_text)
    for field, pattern in PIPE_ENUMERATED.items():
        match = re.search(pattern, text)
        assert match, f"SKILL.md no longer enumerates {field} as a pipe-separated list"
        prose = {token.strip() for token in match.group(1).split("|")}
        assert prose == schema_values(feature_schema, field), (
            f"{field} enumeration drift — prose: {sorted(prose)}, "
            f"schema: {sorted(schema_values(feature_schema, field))}"
        )


def test_word_enumerated_values_appear_in_prose(feature_schema, skill_md_text):
    for field in WORD_PRESENT:
        missing = [
            v for v in schema_values(feature_schema, field)
            if not re.search(rf"(?<![\w-]){re.escape(v)}(?![\w-])", skill_md_text)
        ]
        assert not missing, f"schema {field} values not mentioned in SKILL.md: {missing}"


def test_issue_template_verdicts_match_schema_exactly(feature_schema):
    template = yaml.safe_load(
        (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "teardown-report.yml").read_text()
    )
    verdicts_field = next(
        (item for item in template["body"] if item.get("id") == "verdicts"), None
    )
    assert verdicts_field, "teardown-report.yml no longer has a 'verdicts' field"
    placeholder = verdicts_field["attributes"]["placeholder"]
    in_template = set(re.findall(r"([A-Z]+):", placeholder))
    assert in_template == schema_values(feature_schema, "verdict"), (
        f"verdict drift — template: {sorted(in_template)}, "
        f"schema: {sorted(schema_values(feature_schema, 'verdict'))}"
    )


def test_readme_references_existing_issue_template():
    readme = (REPO_ROOT / "README.md").read_text()
    match = re.search(r"template=([A-Za-z0-9._-]+)", readme)
    assert match, "README no longer links to the issue template"
    template_path = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / match.group(1)
    assert template_path.is_file(), f"README links to missing issue template: {match.group(1)}"
