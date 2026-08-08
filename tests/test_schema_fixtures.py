"""Exercise feature-inventory.schema.json against known-good and
known-bad feature entries. The valid fixtures double as documentation of
what a correct entry looks like; the invalid ones pin down that the
schema actually rejects what it should."""

import json
import re

import jsonschema
import pytest

from conftest import FIXTURES_DIR

VALID_FIXTURES = sorted(FIXTURES_DIR.glob("valid-*.json"))
INVALID_FIXTURES = sorted(FIXTURES_DIR.glob("invalid-*.json"))


def test_fixtures_exist():
    assert VALID_FIXTURES and INVALID_FIXTURES


def test_schema_itself_is_valid(feature_schema):
    jsonschema.Draft202012Validator.check_schema(feature_schema)


@pytest.mark.parametrize("path", VALID_FIXTURES, ids=lambda p: p.name)
def test_valid_fixture_passes(feature_schema, path):
    jsonschema.validate(json.loads(path.read_text()), feature_schema)


@pytest.mark.parametrize("path", INVALID_FIXTURES, ids=lambda p: p.name)
def test_invalid_fixture_fails(feature_schema, path):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(json.loads(path.read_text()), feature_schema)


def test_skill_md_state_file_example(skill_md_text):
    # The Phase 0 code block in SKILL.md defines the teardown.json state
    # file that resumability depends on — it must stay parseable and keep
    # its keys.
    match = re.search(r"```json\n(.*?)```", skill_md_text, re.DOTALL)
    assert match, "SKILL.md no longer contains the Phase 0 teardown.json example"
    state = json.loads(match.group(1))
    assert set(state) == {
        "app", "url", "started", "phase", "preflight",
        "features", "evidence", "extraction", "decisions",
    }
