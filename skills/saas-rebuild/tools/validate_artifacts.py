#!/usr/bin/env python3
"""Validate one SaaS Rebuild teardown directory.

JSON Schema catches local shape errors. This command also checks invariants
that JSON Schema cannot express across files: stable-id uniqueness, evidence
resolution, graph endpoints and process coverage, dataset-lineage isolation,
state references, and preservation file size/digests/path containment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

try:
    import jsonschema
except ImportError as error:  # pragma: no cover - exercised before test deps exist
    raise SystemExit(
        "jsonschema is required; install requirements-dev.txt before validation"
    ) from error


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_ROOT / "templates"
REQUIRED = {
    "teardown": "teardown.json",
    "features": "feature-inventory.json",
    "pairs": "pairs.jsonl",
    "graph": "graph.json",
    "preservation": "preservation-manifest.json",
}
SCHEMAS = {
    "teardown": "teardown-state.schema.json",
    "feature": "feature-inventory.schema.json",
    "pair": "pairs.schema.json",
    "graph": "dependency-graph.schema.json",
    "preservation": "preservation-manifest.schema.json",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: {error}") from error


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    values = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"{path}: {error}") from error
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: {error}") from error
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: JSONL value must be an object")
        values.append(value)
    return values


def duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return repeated


def contained_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"path escapes teardown root: {relative}") from error
    return candidate


class Validation:
    def __init__(self, artifact_root: Path) -> None:
        self.root = artifact_root.resolve()
        self.errors: list[str] = []
        self.schemas = {name: load_json(TEMPLATES / filename) for name, filename in SCHEMAS.items()}

    def error(self, message: str) -> None:
        self.errors.append(message)

    def schema(self, value: Any, schema_name: str, label: str) -> None:
        validator = jsonschema.Draft202012Validator(self.schemas[schema_name])
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path)):
            location = ".".join(str(part) for part in error.absolute_path) or "$"
            self.error(f"{label}:{location}: {error.message}")

    def validate(self) -> int:
        missing = [filename for filename in REQUIRED.values() if not (self.root / filename).is_file()]
        if missing:
            self.errors.extend(f"missing required artifact: {name}" for name in missing)
            return self.finish()

        try:
            state = load_json(self.root / REQUIRED["teardown"])
            features = load_json(self.root / REQUIRED["features"])
            pairs = load_jsonl(self.root / REQUIRED["pairs"])
            graph = load_json(self.root / REQUIRED["graph"])
            preservation = load_json(self.root / REQUIRED["preservation"])
        except ValueError as error:
            self.error(str(error))
            return self.finish()

        self.schema(state, "teardown", "teardown.json")
        if not isinstance(features, list):
            self.error("feature-inventory.json:$: expected an array")
            features = []
        for index, feature in enumerate(features):
            self.schema(feature, "feature", f"feature-inventory.json[{index}]")
        for index, pair in enumerate(pairs):
            self.schema(pair, "pair", f"pairs.jsonl[{index}]")
        self.schema(graph, "graph", "graph.json")
        self.schema(preservation, "preservation", "preservation-manifest.json")

        if not self.errors:
            self.cross_file(state, features, pairs, graph, preservation)
        return self.finish(features=len(features), pairs=len(pairs))

    def cross_file(
        self,
        state: dict[str, Any],
        features: list[dict[str, Any]],
        pairs: list[dict[str, Any]],
        graph: dict[str, Any],
        preservation: dict[str, Any],
    ) -> None:
        feature_ids = [feature["id"] for feature in features]
        repeated = duplicates(feature_ids)
        if repeated:
            self.error(f"duplicate feature ids: {sorted(repeated)}")

        citations = [
            citation
            for feature in features
            for citation in feature.get("evidence", [])
        ]
        evidence_ids = [citation["evidence_id"] for citation in citations]
        repeated = duplicates(evidence_ids)
        if repeated:
            self.error(f"duplicate evidence ids: {sorted(repeated)}")
        evidence_set = set(evidence_ids)
        evidence_map = {citation["evidence_id"]: citation for citation in citations}
        for citation in citations:
            unresolved = set(citation.get("derived_from", [])) - evidence_set
            if unresolved:
                self.error(
                    f"evidence {citation['evidence_id']} has unknown derivation parents: "
                    f"{sorted(unresolved)}"
                )

        for feature in features:
            usage = feature.get("usage")
            usage_citations = [
                citation
                for citation in feature.get("evidence", [])
                if "usage" in citation["supports"]
            ]
            if usage not in (None, "unknown") and not any(
                citation["evidence_class"] == "runtime" for citation in usage_citations
            ):
                self.error(f"feature {feature['id']} has non-unknown usage without runtime evidence")
            if usage == "never" and not any(
                citation["evidence_class"] == "runtime"
                and citation["coverage"]["kind"] == "all-time"
                for citation in usage_citations
            ):
                self.error(f"feature {feature['id']} says never without all-time runtime evidence")
            if usage == "unknown" and feature.get("verdict") not in (None, "DEFER"):
                self.error(f"feature {feature['id']} has unknown usage but verdict is not DEFER")

        node_ids = [node["id"] for node in graph["nodes"]]
        repeated = duplicates(node_ids)
        if repeated:
            self.error(f"duplicate graph node ids: {sorted(repeated)}")
        node_map = {node["id"]: node for node in graph["nodes"]}
        edge_keys = [
            f"{edge['from']}|{edge['to']}|{edge['type']}"
            for edge in graph["edges"]
        ]
        repeated = duplicates(edge_keys)
        if repeated:
            self.error(f"duplicate graph edges: {sorted(repeated)}")
        for edge in graph["edges"]:
            for endpoint in ("from", "to"):
                if edge[endpoint] not in node_map:
                    self.error(f"graph edge references missing {endpoint} node: {edge[endpoint]}")
            unresolved = set(edge["evidence_ids"]) - evidence_set
            if unresolved:
                self.error(f"graph edge {edge['from']}->{edge['to']} has unknown evidence: {sorted(unresolved)}")
            elif not any(
                "dependency" in evidence_map[evidence_id]["supports"]
                for evidence_id in edge["evidence_ids"]
            ):
                self.error(f"graph edge {edge['from']}->{edge['to']} lacks dependency-supporting evidence")
            source_type = node_map.get(edge["from"], {}).get("type")
            target_type = node_map.get(edge["to"], {}).get("type")
            if edge["type"] in {"reads", "writes"} and target_type != "entity":
                self.error(f"{edge['type']} edge must target an entity: {edge['from']}->{edge['to']}")
            if edge["type"] == "joins-on" and (source_type != "report" or target_type != "entity"):
                self.error(f"joins-on edge must be report->entity: {edge['from']}->{edge['to']}")
            if edge["type"] == "triggers" and target_type != "script":
                self.error(f"triggers edge must target a script: {edge['from']}->{edge['to']}")
            if edge["type"] == "exports-to" and target_type != "integration":
                self.error(f"exports-to edge must target an integration: {edge['from']}->{edge['to']}")
            if edge["type"] == "supports" and target_type != "business-process":
                self.error(f"supports edge must target a business process: {edge['from']}->{edge['to']}")

        supports = {
            (edge["from"], edge["to"])
            for edge in graph["edges"]
            if edge["type"] == "supports"
        }
        for feature in features:
            node = node_map.get(feature["id"])
            if node is None:
                self.error(f"feature has no graph node: {feature['id']}")
                continue
            if node.get("type") != "feature":
                self.error(f"feature graph node has wrong type: {feature['id']}")
            if feature.get("verdict") and node.get("verdict") != feature["verdict"]:
                self.error(f"verdict mismatch for {feature['id']}")
            for process in feature.get("business_processes", []):
                if node_map.get(process, {}).get("type") != "business-process":
                    self.error(f"feature {feature['id']} references missing process node: {process}")
                if (feature["id"], process) not in supports:
                    self.error(f"feature {feature['id']} lacks supports edge to {process}")

        pair_ids = [pair["pair_id"] for pair in pairs]
        repeated = duplicates(pair_ids)
        if repeated:
            self.error(f"duplicate pair ids: {sorted(repeated)}")
        roles_by_group: dict[str, set[str]] = {}
        for pair in pairs:
            roles_by_group.setdefault(pair["split_group"], set()).add(pair["dataset_role"])
            if pair["provenance"]["teardown_id"] != state["teardown_id"]:
                self.error(f"pair {pair['pair_id']} teardown_id does not match state")
        leaks = {group: roles for group, roles in roles_by_group.items() if len(roles) > 1}
        if leaks:
            self.error(f"split_group appears in multiple dataset roles: {leaks}")

        for field, key in (
            ("preflight", "id"),
            ("decisions", "id"),
        ):
            values = [item[key] for item in state[field]]
            repeated = duplicates(values)
            if repeated:
                self.error(f"duplicate teardown {field} ids: {sorted(repeated)}")

        for name, relative in state["artifacts"].items():
            try:
                path = contained_path(self.root, relative)
            except ValueError as error:
                self.error(f"state artifact {name}: {error}")
                continue
            if not path.is_file():
                self.error(f"state artifact {name} does not exist: {relative}")

        if preservation["teardown_id"] != state["teardown_id"]:
            self.error("preservation teardown_id does not match state")
        artifact_ids = [artifact["id"] for artifact in preservation["artifacts"]]
        repeated = duplicates(artifact_ids)
        if repeated:
            self.error(f"duplicate preservation artifact ids: {sorted(repeated)}")
        file_paths: list[str] = []
        for artifact in preservation["artifacts"]:
            for file_entry in artifact.get("files", []):
                file_paths.append(file_entry["path"])
                try:
                    path = contained_path(self.root, file_entry["path"])
                except ValueError as error:
                    self.error(f"preservation artifact {artifact['id']}: {error}")
                    continue
                if not path.is_file():
                    self.error(f"preserved file does not exist: {file_entry['path']}")
                    continue
                data = path.read_bytes()
                if len(data) != file_entry["bytes"]:
                    self.error(f"preserved file size mismatch: {file_entry['path']}")
                if hashlib.sha256(data).hexdigest() != file_entry["sha256"]:
                    self.error(f"preserved file digest mismatch: {file_entry['path']}")
            if (
                artifact["category"] == "replay-corpus"
                and any(item["path"] == state["artifacts"]["pairs"] for item in artifact.get("files", []))
                and artifact.get("record_count") != len(pairs)
            ):
                self.error("replay-corpus record_count does not match pairs.jsonl")
        repeated = duplicates(file_paths)
        if repeated:
            self.error(f"preserved file appears in multiple artifacts: {sorted(repeated)}")

    def finish(self, *, features: int = 0, pairs: int = 0) -> int:
        if self.errors:
            for error in self.errors:
                print(f"ERROR: {error}", file=sys.stderr)
            print(f"artifact validation failed ({len(self.errors)} errors)", file=sys.stderr)
            return 1
        print(f"artifact validation passed ({features} features, {pairs} pairs)")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_root", type=Path)
    args = parser.parse_args()
    if not args.artifact_root.is_dir():
        parser.error(f"not a directory: {args.artifact_root}")
    return Validation(args.artifact_root).validate()


if __name__ == "__main__":
    raise SystemExit(main())
