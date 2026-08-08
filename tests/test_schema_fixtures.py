"""Executable invariants for the feature and teardown-state contracts."""

import json
import re

import jsonschema
import pytest

from conftest import FIXTURES_DIR, SKILL_DIR


VALID_FIXTURES = sorted(FIXTURES_DIR.glob("valid-*.json"))
FULL_FIXTURE = FIXTURES_DIR / "valid-full.json"
STATE_SCHEMA_PATH = SKILL_DIR / "templates" / "teardown-state.schema.json"


def _drop_schema(value):
    value.pop("schema_version")


def _bad_kind(value):
    value["kind"] = "dashboard"


def _extra_property(value):
    value["unreviewed_claim"] = True


def _drop_kind(value):
    value.pop("kind")


def _bad_record_count(value):
    value["observed_signals"]["record_count"] = "312"


def _usage_without_evidence(value):
    value.pop("evidence")


def _verdict_without_why(value):
    value.pop("why")


def _citation_without_source(value):
    value["evidence"][0].pop("source")


def _bad_plane(value):
    value["evidence"][0]["plane"] = "memory"


def _critical_without_process(value):
    value.pop("business_processes")


def _verdict_without_supporting_citation(value):
    for citation in value["evidence"]:
        citation["supports"] = [s for s in citation["supports"] if s != "verdict"]


def _usage_without_supporting_citation(value):
    for citation in value["evidence"]:
        citation["supports"] = [s for s in citation["supports"] if s != "usage"]


def _window_without_end(value):
    value["evidence"][1]["coverage"].pop("end")


def _duplicate_entity(value):
    value["data_entities"].append(value["data_entities"][0])


INVALID_MUTATIONS = [
    ("missing-schema-version", _drop_schema),
    ("bad-kind", _bad_kind),
    ("extra-property", _extra_property),
    ("missing-kind", _drop_kind),
    ("record-count-string", _bad_record_count),
    ("usage-without-evidence", _usage_without_evidence),
    ("verdict-without-why", _verdict_without_why),
    ("citation-without-source", _citation_without_source),
    ("bad-evidence-plane", _bad_plane),
    ("critical-without-process", _critical_without_process),
    ("verdict-without-supporting-citation", _verdict_without_supporting_citation),
    ("usage-without-supporting-citation", _usage_without_supporting_citation),
    ("window-without-end", _window_without_end),
    ("duplicate-entity", _duplicate_entity),
]


def test_valid_fixtures_exist():
    assert VALID_FIXTURES


def test_schema_itself_is_valid(feature_schema):
    jsonschema.Draft202012Validator.check_schema(feature_schema)


@pytest.mark.parametrize("path", VALID_FIXTURES, ids=lambda path: path.name)
def test_valid_fixture_passes(feature_schema, path):
    jsonschema.Draft202012Validator(feature_schema).validate(json.loads(path.read_text()))


@pytest.mark.parametrize(
    "case,mutation", INVALID_MUTATIONS, ids=[case for case, _ in INVALID_MUTATIONS]
)
def test_invalid_mutation_fails(feature_schema, case, mutation):
    value = json.loads(FULL_FIXTURE.read_text())
    mutation(value)
    errors = list(jsonschema.Draft202012Validator(feature_schema).iter_errors(value))
    assert errors, f"mutation {case} unexpectedly passed"


def test_skill_md_state_example_validates(skill_md_text):
    match = re.search(r"```json\n(.*?)```", skill_md_text, re.DOTALL)
    assert match, "SKILL.md needs a Phase 0 teardown.json example"
    state = json.loads(match.group(1))
    state_schema = json.loads(STATE_SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(state_schema)
    jsonschema.Draft202012Validator(state_schema).validate(state)
    assert state["artifacts"]["feature_inventory"] == "feature-inventory.json"
    assert state["artifacts"]["pairs"] == "pairs.jsonl"
