#!/usr/bin/env python3
"""Apply the one-time SaaS Rebuild 0.9.0 -> 0.10.0 contract bump."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "saas-rebuild"
TEMPLATES = SKILL / "templates"
OLD = "0.9.0"
NEW = "0.10.0"

MEASURE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["metric", "value", "unit"],
    "properties": {
        "metric": {"type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"},
        "value": {"type": "number"},
        "unit": {"type": "string", "minLength": 1},
        "window_start": {"type": ["string", "null"], "pattern": r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$"},
        "window_end": {"type": ["string", "null"], "pattern": r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$"},
    },
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_schema(path: Path) -> None:
    schema = read(path)
    schema["properties"]["schema_version"]["const"] = NEW
    if path.name == "extraction-recipe.schema.json":
        schema["$id"] = "https://github.com/chrbailey/saas-rebuild/schemas/extraction-recipe-v0.10.json"
    write(path, schema)


def update_feature_and_pairs() -> None:
    feature_path = TEMPLATES / "feature-inventory.schema.json"
    pairs_path = TEMPLATES / "pairs.schema.json"
    feature = read(feature_path)
    pairs = read(pairs_path)
    feature["$defs"]["citation"]["properties"]["measure"] = MEASURE
    pairs["$defs"]["citation"]["properties"]["measure"] = MEASURE
    pairs["properties"]["provenance"]["properties"]["model_assist"] = {
        "type": "array",
        "uniqueItems": True,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["annotation_id", "question_id", "effect"],
            "properties": {
                "annotation_id": {"type": "string", "minLength": 1},
                "question_id": {"type": "string", "minLength": 1},
                "effect": {"enum": ["flag", "veto", "reject", "prioritize", "suggest", "none"]},
            },
        },
    }
    write(feature_path, feature)
    write(pairs_path, pairs)


def update_teardown() -> None:
    path = TEMPLATES / "teardown-state.schema.json"
    schema = read(path)
    boundary = schema["properties"]["data_boundary"]["properties"]
    boundary["source_classes"] = {
        "type": "object",
        "additionalProperties": {"enum": ["public", "internal", "confidential", "restricted"]},
    }
    endpoint_status = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "ref"],
        "properties": {
            "status": {"enum": ["unknown", "not-in-force", "in-force"]},
            "ref": {"type": ["string", "null"]},
        },
    }
    boundary["model_endpoints"] = {
        "type": "array",
        "uniqueItems": True,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "vendor", "endpoint", "boundary", "allowed_data_classes", "purposes", "zdr", "baa", "transfer_mechanism", "training_on_customer_data", "terms_version", "approved_by", "approved_at"],
            "properties": {
                "id": {"type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"},
                "vendor": {"type": "string", "minLength": 1},
                "endpoint": {"type": "string", "const": "https://api.typesafe.ai/v1/systemone"},
                "boundary": {"enum": ["local", "self-hosted", "vendor-cloud", "mixed"]},
                "allowed_data_classes": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"enum": ["public", "internal", "confidential", "restricted"]}},
                "purposes": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}},
                "zdr": endpoint_status,
                "baa": endpoint_status,
                "transfer_mechanism": {"type": ["string", "null"]},
                "training_on_customer_data": {"enum": ["unknown", "yes", "no"]},
                "terms_version": {"type": "string", "minLength": 1},
                "approved_by": {"type": "string", "minLength": 1},
                "approved_at": {"$ref": "#/$defs/timestamp"},
            },
        },
    }
    preflight_ids = schema["properties"]["preflight"]["items"]["properties"]["id"]["enum"]
    if "model-vendor-review" not in preflight_ids:
        preflight_ids.append("model-vendor-review")
    schema["properties"]["decisions"]["items"]["properties"]["annotation_ids"] = {
        "type": "array", "uniqueItems": True, "items": {"type": "string", "minLength": 1}
    }
    write(path, schema)


def update_preservation() -> None:
    path = TEMPLATES / "preservation-manifest.schema.json"
    schema = read(path)
    categories = schema["properties"]["artifacts"]["items"]["properties"]["category"]["enum"]
    if "model-io" not in categories:
        categories.append("model-io")
    write(path, schema)


def replace_versions() -> None:
    targets = [
        SKILL / "SKILL.md",
        SKILL / "references" / "dependency-graph.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "tests" / "test_contract_dates.py",
    ]
    targets += sorted((SKILL / "corpus" / "extraction-recipes").glob("*.json"))
    targets += sorted((ROOT / "examples" / "synthetic-crm").glob("*.json"))
    targets += [ROOT / "examples" / "synthetic-crm" / "pairs.jsonl"]
    targets += sorted((ROOT / "tests" / "fixtures").glob("valid-*.json"))
    targets += sorted((ROOT / "tests" / "fixtures" / "pairs").glob("valid-*.json"))
    for path in targets:
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(OLD, NEW), encoding="utf-8")

    versions = read(ROOT / "skill-versions.json")
    versions["saas-rebuild"] = NEW
    write(ROOT / "skill-versions.json", versions)
    plugin = read(ROOT / ".claude-plugin" / "plugin.json")
    plugin["version"] = NEW
    write(ROOT / ".claude-plugin" / "plugin.json", plugin)


def main() -> None:
    for path in sorted(TEMPLATES.glob("*.schema.json")):
        update_schema(path)
    update_feature_and_pairs()
    update_teardown()
    update_preservation()
    replace_versions()
    print("migrated SaaS Rebuild contracts to 0.10.0")


if __name__ == "__main__":
    main()
