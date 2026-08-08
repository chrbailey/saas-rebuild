"""Exercise pairs.schema.json — the contract for one line of pairs.jsonl,
the paired-training-data output — against known-good and known-bad pairs,
and pin its citation shape to the feature schema's so the two cannot
drift apart."""

import json

import jsonschema
import pytest

from conftest import FIXTURES_DIR, SKILL_DIR

PAIRS_SCHEMA_PATH = SKILL_DIR / "templates" / "pairs.schema.json"
PAIRS_FIXTURES = FIXTURES_DIR / "pairs"

VALID = sorted(PAIRS_FIXTURES.glob("valid-*.json"))
INVALID = sorted(PAIRS_FIXTURES.glob("invalid-*.json"))


@pytest.fixture(scope="module")
def pairs_schema():
    return json.loads(PAIRS_SCHEMA_PATH.read_text())


def test_fixtures_exist():
    assert VALID and INVALID


def test_schema_itself_is_valid(pairs_schema):
    jsonschema.Draft202012Validator.check_schema(pairs_schema)


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.name)
def test_valid_pair_passes(pairs_schema, path):
    jsonschema.validate(json.loads(path.read_text()), pairs_schema)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.name)
def test_invalid_pair_fails(pairs_schema, path):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(json.loads(path.read_text()), pairs_schema)


def test_citation_shape_matches_feature_schema(pairs_schema, feature_schema):
    # pairs.schema.json duplicates the citation shape in $defs to stay
    # self-contained; this pin is what keeps the duplicate honest.
    def stripped(node):
        return {k: v for k, v in node.items() if k != "description"}

    pairs_citation = stripped(pairs_schema["$defs"]["citation"])
    feature_citation = stripped(feature_schema["properties"]["evidence"]["items"])
    pairs_citation["properties"] = {
        k: stripped(v) for k, v in pairs_citation["properties"].items()
    }
    feature_citation["properties"] = {
        k: stripped(v) for k, v in feature_citation["properties"].items()
    }
    assert pairs_citation == feature_citation
