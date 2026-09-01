"""Every date and timestamp pattern in the artifact schemas is anchored and
calendar-plausible: month 01-12, day 01-31, hour 00-23, minute/second 00-59,
and nothing before or after the value."""

import json
import re

import jsonschema
import pytest

from conftest import FIXTURES_DIR, SKILL_DIR

TEMPLATES = SKILL_DIR / "templates"
ARTIFACT_SCHEMAS = sorted(
    path for path in TEMPLATES.glob("*.schema.json") if path.name != "extraction-recipe.schema.json"
)

ACCEPTED_SOMEWHERE = [
    "2026-01-31",
    "2026-12-01T23:59:59Z",
    "2026-02-28T00:00:00.123+05:30",
]
REJECTED_EVERYWHERE = [
    "2026-13-01",
    "2026-00-10",
    "2026-01-32",
    "2026-01-00",
    "2026-1-01",
    "2026-01-01T24:00:00Z",
    "2026-01-01T12:60:00Z",
    "2026-01-01T12:00:61Z",
    "2026-01-01T12:00:00",
    "2026-01-01T12:00:00+24:00",
    "2026-01-01 or thereabouts",
    "2026-01-01T12:00:00Z; then it drifted",
    "on 2026-01-01",
]


def date_patterns(node, location="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "pattern" and isinstance(value, str) and value.startswith("^\\d{4}-"):
                yield location, value
            else:
                yield from date_patterns(value, f"{location}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from date_patterns(value, f"{location}[{index}]")


def all_patterns():
    for path in ARTIFACT_SCHEMAS:
        found = list(date_patterns(json.loads(path.read_text(encoding="utf-8"))))
        assert found, f"{path.name} has no date patterns to check"
        for location, pattern in found:
            yield pytest.param(pattern, id=f"{path.name}:{location}")


@pytest.mark.parametrize("pattern", list(all_patterns()))
def test_date_pattern_is_anchored_and_calendar_plausible(pattern):
    # JSON Schema `pattern` is an unanchored search, so the pattern itself
    # must carry both anchors; re.search mirrors what validators do.
    assert any(re.search(pattern, value) for value in ACCEPTED_SOMEWHERE), pattern
    leaked = [value for value in REJECTED_EVERYWHERE if re.search(pattern, value)]
    assert not leaked, f"{pattern} accepts {leaked}"


def load_schema(name):
    return json.loads((TEMPLATES / name).read_text(encoding="utf-8"))


def errors(schema, value):
    return list(jsonschema.Draft202012Validator(schema).iter_errors(value))


def test_feature_coverage_rejects_impossible_dates():
    schema = load_schema("feature-inventory.schema.json")
    feature = json.loads((FIXTURES_DIR / "valid-full.json").read_text(encoding="utf-8"))
    assert not errors(schema, feature)
    feature["evidence"][1]["coverage"]["end"] = "2026-13-99"
    assert errors(schema, feature)


def test_replay_as_of_is_anchored_at_the_end():
    schema = load_schema("pairs.schema.json")
    pair = json.loads((FIXTURES_DIR / "pairs" / "valid-replay.json").read_text(encoding="utf-8"))
    assert not errors(schema, pair)
    pair["replay_context"]["as_of"] = "2026-07-01"
    assert not errors(schema, pair), "a bare date is a valid as_of"
    pair["replay_context"]["as_of"] = "2026-07-01T12:00:00Z; config drifted after"
    assert errors(schema, pair)


def test_preservation_date_range_rejects_free_text_after_t():
    schema = load_schema("preservation-manifest.schema.json")
    manifest = {
        "schema_version": "0.7.0",
        "teardown_id": "t",
        "generated_at": "2026-08-01T16:45:00Z",
        "artifacts": [
            {
                "id": "a",
                "category": "other",
                "status": "blocked",
                "source": "s",
                "route": "r",
                "sensitivity": "public",
                "date_range": {"start": "2026-06-01", "end": "2026-07-30T23:59:59Z"},
                "gap": {"reason": "x", "accepted_by": "y", "accepted_at": "2026-08-01T16:44:00Z"},
            }
        ],
    }
    assert not errors(schema, manifest)
    manifest["artifacts"][0]["date_range"]["end"] = "2026-07-30Tapproximately"
    assert errors(schema, manifest)
