#!/usr/bin/env python3
"""Apply the one-time SaaS Rebuild 0.10.0 -> 0.11.0 bump to this repository.

Maintainers only. This rewrites the repository's own schemas, corpus recipes,
examples, fixtures, and the annotation writer; it never touches a user's
teardown directory. For that, follow docs/migration-v0.11.md. It refuses to
run on a tree not at 0.10.0, because re-running would reformat schemas that
were refined by hand afterwards. The interviews schema is authored by hand.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "saas-rebuild"
TEMPLATES = SKILL / "templates"
OLD = "0.10.0"
NEW = "0.11.0"

STATEMENT_IDS = {
    "type": "array",
    "minItems": 1,
    "uniqueItems": True,
    "items": {"type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"},
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_schema(path: Path) -> None:
    # Text replacement keeps hand-formatted schemas byte-stable apart from
    # the version; a JSON round trip would reflow model-annotations.
    text = path.read_text(encoding="utf-8")
    text = text.replace(f'"const": "{OLD}"', f'"const": "{NEW}"')
    text = text.replace("extraction-recipe-v0.10.json", "extraction-recipe-v0.11.json")
    path.write_text(text, encoding="utf-8")
    if read(path)["properties"]["schema_version"]["const"] != NEW:
        raise SystemExit(f"{path.name}: schema_version const was not bumped")


def update_citations() -> None:
    for name in ("feature-inventory.schema.json", "pairs.schema.json"):
        path = TEMPLATES / name
        schema = read(path)
        schema["$defs"]["citation"]["properties"]["statement_ids"] = STATEMENT_IDS
        write(path, schema)


def update_teardown() -> None:
    path = TEMPLATES / "teardown-state.schema.json"
    schema = read(path)
    schema["properties"]["artifacts"]["properties"]["interviews"] = {"type": "string", "minLength": 1}
    write(path, schema)


def replace_versions() -> None:
    targets = [
        SKILL / "SKILL.md",
        SKILL / "references" / "dependency-graph.md",
        SKILL / "tools" / "systemone" / "runner.py",
        ROOT / "CONTRIBUTING.md",
        ROOT / "tests" / "test_contract_dates.py",
        ROOT / "tests" / "test_validator_model_annotations.py",
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


def main() -> int:
    current = read(ROOT / "skill-versions.json").get("saas-rebuild")
    if current != OLD:
        print(
            f"refusing: saas-rebuild is at {current}, not {OLD}; this one-time "
            "repository migration has already been applied. To migrate a "
            "teardown directory, follow docs/migration-v0.11.md.",
            file=sys.stderr,
        )
        return 1
    for path in sorted(TEMPLATES.glob("*.schema.json")):
        update_schema(path)
    update_citations()
    update_teardown()
    replace_versions()
    print("migrated SaaS Rebuild contracts to 0.11.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
