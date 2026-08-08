"""Executable invariants for behavioral cases and leakage metadata."""

from copy import deepcopy
import json

import jsonschema
import pytest

from conftest import FIXTURES_DIR, REPO_ROOT, SKILL_DIR


PAIRS_SCHEMA_PATH = SKILL_DIR / "templates" / "pairs.schema.json"
PAIRS_FIXTURES = FIXTURES_DIR / "pairs"
VALID = sorted(PAIRS_FIXTURES.glob("valid-*.json"))
JUDGMENT = PAIRS_FIXTURES / "valid-judgment.json"
REPLAY = PAIRS_FIXTURES / "valid-replay.json"


@pytest.fixture(scope="module")
def pairs_schema():
    return json.loads(PAIRS_SCHEMA_PATH.read_text())


def test_valid_fixtures_exist():
    assert VALID


def test_public_pair_fixtures_are_not_marked_raw_local_only():
    pairs = [json.loads(path.read_text()) for path in VALID]
    example = REPO_ROOT / "examples" / "synthetic-crm" / "pairs.jsonl"
    pairs.extend(json.loads(line) for line in example.read_text().splitlines() if line)
    assert all(pair["sanitization_tier"] != "raw-local-only" for pair in pairs)


def test_schema_itself_is_valid(pairs_schema):
    jsonschema.Draft202012Validator.check_schema(pairs_schema)


@pytest.mark.parametrize("path", VALID, ids=lambda path: path.name)
def test_valid_pair_passes(pairs_schema, path):
    jsonschema.Draft202012Validator(pairs_schema).validate(json.loads(path.read_text()))


def invalid_pairs():
    judgment = json.loads(JUDGMENT.read_text())
    replay = json.loads(REPLAY.read_text())

    cases = []
    for field in ("schema_version", "pair_id", "dataset_role", "split_group", "provenance"):
        value = deepcopy(judgment)
        value.pop(field)
        cases.append((f"missing-{field}", value))

    value = deepcopy(judgment)
    value["pair_type"] = "opinion"
    cases.append(("bad-pair-type", value))

    value = deepcopy(judgment)
    value["unexpected"] = True
    cases.append(("extra-property", value))

    value = deepcopy(judgment)
    value["provenance"]["phase"] = 6
    cases.append(("phase-out-of-range", value))

    value = deepcopy(judgment)
    value["provenance"]["created_at"] = "2026-07-28"
    cases.append(("bad-created-at", value))

    value = deepcopy(judgment)
    value.pop("sanitization_review")
    cases.append(("shareable-without-review", value))

    value = deepcopy(judgment)
    value["sanitization_review"]["status"] = "pending"
    cases.append(("shareable-review-pending", value))

    value = deepcopy(judgment)
    value["dataset_role"] = "holdout-eval"
    cases.append(("analyst-as-holdout-gold", value))

    value = deepcopy(judgment)
    value.pop("evidence")
    cases.append(("judgment-without-evidence", value))

    value = deepcopy(replay)
    value["label_authority"] = "analyst"
    cases.append(("replay-with-analyst-label", value))

    value = deepcopy(replay)
    value.pop("replay_context")
    cases.append(("replay-without-context", value))

    value = deepcopy(replay)
    value["replay_context"]["side_effect_free_verified"] = False
    cases.append(("replay-side-effects-not-isolated", value))
    return cases


@pytest.mark.parametrize(
    "case,value", invalid_pairs(), ids=[case for case, _ in invalid_pairs()]
)
def test_invalid_pair_fails(pairs_schema, case, value):
    errors = list(jsonschema.Draft202012Validator(pairs_schema).iter_errors(value))
    assert errors, f"case {case} unexpectedly passed"


def test_citation_shape_matches_feature_schema(pairs_schema, feature_schema):
    def strip_descriptions(node):
        if isinstance(node, dict):
            return {
                key: strip_descriptions(value)
                for key, value in node.items()
                if key != "description"
            }
        if isinstance(node, list):
            return [strip_descriptions(value) for value in node]
        return node

    assert strip_descriptions(pairs_schema["$defs"]["citation"]) == strip_descriptions(
        feature_schema["$defs"]["citation"]
    )
