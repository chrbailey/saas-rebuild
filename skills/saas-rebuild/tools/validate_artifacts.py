#!/usr/bin/env python3
"""Validate one SaaS Rebuild teardown directory.

JSON Schema catches local shape errors. This command also checks invariants
that JSON Schema cannot express across files: stable-id uniqueness, evidence
resolution (graph edges, teardown decisions, and pair citations all resolve
to the feature inventory, and a pair's copy of a citation must equal its
inventory definition), graph endpoints and process coverage, verdict parity
between inventory and graph in both directions, dataset-lineage isolation,
state references to the validated files, and preservation file
size/digests/path containment with normalized path comparison; and locked
success-profile to scorecard identity, evidence coverage, score arithmetic,
assessment coverage, and must-have gate status.
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
    "success": "success-profile.json",
    "scorecard": "evaluation-scorecard.json",
}
SCHEMAS = {
    "teardown": "teardown-state.schema.json",
    "feature": "feature-inventory.schema.json",
    "pair": "pairs.schema.json",
    "graph": "dependency-graph.schema.json",
    "preservation": "preservation-manifest.schema.json",
    "success": "success-profile.schema.json",
    "scorecard": "evaluation-scorecard.schema.json",
    "annotation": "model-annotations.schema.json",
}
# teardown.json `artifacts` keys that must name the file this command
# validated; a state pointing elsewhere would make the validated file and the
# declared artifact silently differ.
STATE_ARTIFACTS = {
    "feature_inventory": REQUIRED["features"],
    "pairs": REQUIRED["pairs"],
    "graph": REQUIRED["graph"],
    "preservation_manifest": REQUIRED["preservation"],
    "success_profile": REQUIRED["success"],
    "evaluation_scorecard": REQUIRED["scorecard"],
    "model_annotations": "model-annotations.jsonl",
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
            success = load_json(self.root / REQUIRED["success"])
            scorecard = load_json(self.root / REQUIRED["scorecard"])
            annotation_path = self.root / "model-annotations.jsonl"
            annotations = load_jsonl(annotation_path) if annotation_path.is_file() else []
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
        self.schema(success, "success", "success-profile.json")
        self.schema(scorecard, "scorecard", "evaluation-scorecard.json")
        for index, annotation in enumerate(annotations):
            self.schema(annotation, "annotation", f"model-annotations.jsonl[{index}]")

        if not self.errors:
            self.cross_file(state, features, pairs, graph, preservation, success, scorecard, annotations)
        return self.finish(features=len(features), pairs=len(pairs))

    def cross_file(
        self,
        state: dict[str, Any],
        features: list[dict[str, Any]],
        pairs: list[dict[str, Any]],
        graph: dict[str, Any],
        preservation: dict[str, Any],
        success: dict[str, Any],
        scorecard: dict[str, Any],
        annotations: list[dict[str, Any]],
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
        globally_allowed = set(state["data_boundary"]["allowed_data_classes"])
        for citation in citations:
            if citation["sensitivity"] not in globally_allowed:
                self.error(
                    f"evidence {citation['evidence_id']} sensitivity is outside the approved boundary: "
                    f"{citation['sensitivity']}"
                )
            unresolved = set(citation.get("derived_from", [])) - evidence_set
            if unresolved:
                self.error(
                    f"evidence {citation['evidence_id']} has unknown derivation parents: "
                    f"{sorted(unresolved)}"
                )

        # The feature inventory is the evidence registry. A pair carries a
        # copy of each citation it relies on; the copy must be the same
        # observation, field for field, or the pair is citing evidence the
        # inventory never recorded.
        for pair in pairs:
            for citation in pair.get("evidence", []):
                evidence_id = citation["evidence_id"]
                definition = evidence_map.get(evidence_id)
                if definition is None:
                    self.error(f"pair {pair['pair_id']} cites unknown evidence: {evidence_id}")
                    continue
                unresolved = set(citation.get("derived_from", [])) - evidence_set
                if unresolved:
                    self.error(
                        f"pair {pair['pair_id']} citation {evidence_id} has unknown "
                        f"derivation parents: {sorted(unresolved)}"
                    )
                differing = sorted(
                    field
                    for field in set(citation) | set(definition)
                    if citation.get(field) != definition.get(field)
                )
                if differing:
                    self.error(
                        f"pair {pair['pair_id']} citation {evidence_id} differs from its "
                        f"feature-inventory definition in: {differing}"
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
        feature_map = {feature["id"]: feature for feature in features}
        for node in graph["nodes"]:
            if node.get("type") == "feature" and node["id"] not in feature_map:
                self.error(f"graph feature node has no inventory entry: {node['id']}")
        for feature in features:
            node = node_map.get(feature["id"])
            if node is None:
                self.error(f"feature has no graph node: {feature['id']}")
                continue
            if node.get("type") != "feature":
                self.error(f"feature graph node has wrong type: {feature['id']}")
            if node.get("verdict") != feature.get("verdict"):
                self.error(
                    f"verdict mismatch for {feature['id']}: "
                    f"inventory={feature.get('verdict')} graph={node.get('verdict')}"
                )
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
            if pair["dataset_role"] == "holdout-eval" and pair["provenance"].get("model_assist"):
                self.error(f"holdout pair {pair['pair_id']} must not contain model assistance")
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
        for decision in state["decisions"]:
            unresolved = set(decision["evidence_ids"]) - evidence_set
            if unresolved:
                self.error(
                    f"teardown decision {decision['id']} has unknown evidence: {sorted(unresolved)}"
                )

        annotation_ids = [annotation["annotation_id"] for annotation in annotations]
        repeated = duplicates(annotation_ids)
        if repeated:
            self.error(f"duplicate model annotation ids: {sorted(repeated)}")
        annotation_set = set(annotation_ids)
        endpoint_list = state["data_boundary"].get("model_endpoints", [])
        endpoint_ids = [endpoint["id"] for endpoint in endpoint_list]
        repeated = duplicates(endpoint_ids)
        if repeated:
            self.error(f"duplicate model endpoint ids: {sorted(repeated)}")
        endpoint_map = {endpoint["id"]: endpoint for endpoint in endpoint_list}
        graph_edge_ids = {
            f"{edge['from']}|{edge['to']}|{edge['type']}" for edge in graph["edges"]
        }
        target_sets = {
            "feature": set(feature_ids),
            "citation": evidence_set,
            "graph-edge": graph_edge_ids,
            "pair": set(pair_ids),
        }
        # Only an explicit "no" clears PHI or EU personal data; absent or
        # "unknown" fails closed, matching the runner's boundary gate.
        regulated = state["data_boundary"].get("regulated_data") or {}
        phi_possible = regulated.get("phi") != "no"
        eu_possible = regulated.get("eu_personal_data") != "no"
        open_effects: dict[tuple[str, str], set[str]] = {}
        for annotation in annotations:
            endpoint = endpoint_map.get(annotation["endpoint_id"])
            if endpoint is None:
                self.error(
                    f"annotation {annotation['annotation_id']} references unknown endpoint: "
                    f"{annotation['endpoint_id']}"
                )
            else:
                sent = set(annotation["sent_data_classes"])
                refused = sent - globally_allowed | sent - set(endpoint["allowed_data_classes"])
                if refused:
                    self.error(
                        f"annotation {annotation['annotation_id']} sent unapproved data classes: "
                        f"{sorted(refused)}"
                    )
                if phi_possible and (endpoint.get("baa") or {}).get("status") != "in-force":
                    self.error(
                        f"annotation {annotation['annotation_id']} was produced while PHI is "
                        "present or undeclared, without a BAA in force"
                    )
                if eu_possible and not endpoint.get("transfer_mechanism"):
                    self.error(
                        f"annotation {annotation['annotation_id']} was produced while EU personal "
                        "data is present or undeclared, without a transfer mechanism"
                    )
            targets = target_sets.get(annotation["target_kind"])
            if targets is None or annotation["target_id"] not in targets:
                self.error(
                    f"annotation {annotation['annotation_id']} target does not resolve: "
                    f"{annotation['target_kind']}:{annotation['target_id']}"
                )
            if annotation["resolution"]["status"] == "open":
                key = (annotation["target_kind"], annotation["target_id"])
                open_effects.setdefault(key, set()).add(annotation["effect"])

        for feature in features:
            effects = open_effects.get(("feature", feature["id"]), set())
            if feature.get("verdict") == "DROP" and effects & {"flag", "veto"}:
                self.error(f"feature {feature['id']} is DROP despite an open model flag or veto")
        for pair in pairs:
            effects = open_effects.get(("pair", pair["pair_id"]), set())
            review = pair.get("sanitization_review") or {}
            if (
                pair["sanitization_tier"] == "sanitized-shareable"
                and review.get("status") == "approved"
                and effects & {"reject", "veto"}
            ):
                self.error(
                    f"pair {pair['pair_id']} is shareable despite an open model sanitization rejection"
                )
            if (
                pair["sanitization_tier"] == "sanitized-shareable"
                and review.get("status") == "approved"
                and review.get("method") == "model-prescreen-reject"
            ):
                self.error(f"pair {pair['pair_id']} cannot be approved by a rejected model prescreen")

        for decision in state["decisions"]:
            unresolved = set(decision.get("annotation_ids", [])) - annotation_set
            if unresolved:
                self.error(
                    f"teardown decision {decision['id']} has unknown annotations: {sorted(unresolved)}"
                )
        for pair in pairs:
            assisted = {
                item["annotation_id"] for item in pair["provenance"].get("model_assist", [])
            }
            unresolved = assisted - annotation_set
            if unresolved:
                self.error(f"pair {pair['pair_id']} has unknown model annotations: {sorted(unresolved)}")

        # The benchmark is locked before evidence collection and the scorecard
        # is a complete, reproducible crosswalk against that exact file.
        if success["teardown_id"] != state["teardown_id"]:
            self.error("success-profile teardown_id does not match state")
        if scorecard["teardown_id"] != state["teardown_id"]:
            self.error("evaluation-scorecard teardown_id does not match state")
        if success["app"]["slug"] != state["app"]["slug"]:
            self.error("success-profile app slug does not match state")

        criteria = success["criteria"]
        criterion_ids = [criterion["id"] for criterion in criteria]
        repeated = duplicates(criterion_ids)
        if repeated:
            self.error(f"duplicate success-profile criterion ids: {sorted(repeated)}")
        criterion_map = {criterion["id"]: criterion for criterion in criteria}

        entries = scorecard["entries"]
        entry_ids = [entry["criterion_id"] for entry in entries]
        repeated = duplicates(entry_ids)
        if repeated:
            self.error(f"duplicate evaluation-scorecard criterion ids: {sorted(repeated)}")
        missing_entries = sorted(set(criterion_ids) - set(entry_ids))
        extra_entries = sorted(set(entry_ids) - set(criterion_ids))
        if missing_entries:
            self.error(f"evaluation-scorecard is missing criteria: {missing_entries}")
        if extra_entries:
            self.error(f"evaluation-scorecard has unknown criteria: {extra_entries}")

        entry_map = {entry["criterion_id"]: entry for entry in entries}
        for entry in entries:
            unresolved = set(entry["evidence_ids"]) - evidence_set
            if unresolved:
                self.error(
                    f"evaluation criterion {entry['criterion_id']} has unknown evidence: "
                    f"{sorted(unresolved)}"
                )
                continue
            if entry["criterion_id"] not in criterion_map:
                continue
            if entry["status"] == "unknown":
                continue
            required_classes = set(
                criterion_map[entry["criterion_id"]]["acceptance"]["evidence_classes"]
            )
            present_classes = {
                evidence_map[evidence_id]["evidence_class"]
                for evidence_id in entry["evidence_ids"]
            }
            absent_classes = sorted(required_classes - present_classes)
            if absent_classes:
                self.error(
                    f"evaluation criterion {entry['criterion_id']} lacks required evidence "
                    f"classes: {absent_classes}"
                )

        success_bytes = (self.root / REQUIRED["success"]).read_bytes()
        expected_digest = hashlib.sha256(success_bytes).hexdigest()
        if scorecard["benchmark"]["sha256"] != expected_digest:
            self.error("evaluation-scorecard benchmark digest does not match success-profile.json")

        summary = scorecard["summary"]
        total_weight = sum(criterion["weight"] for criterion in criteria)
        assessed = [
            criterion
            for criterion in criteria
            if criterion["id"] in entry_map and entry_map[criterion["id"]]["score"] is not None
        ]
        assessed_weight = sum(criterion["weight"] for criterion in assessed)
        coverage = round(100 * assessed_weight / total_weight, 2)
        weighted = (
            round(
                sum(
                    criterion["weight"] * entry_map[criterion["id"]]["score"]
                    for criterion in assessed
                )
                / assessed_weight,
                2,
            )
            if assessed_weight
            else None
        )
        unknown = sorted(
            criterion["id"]
            for criterion in criteria
            if entry_map.get(criterion["id"], {}).get("status") == "unknown"
        )
        must_gaps = sorted(
            criterion["id"]
            for criterion in criteria
            if criterion["priority"] == "must"
            and entry_map.get(criterion["id"], {}).get("status") != "met"
        )
        failed = any(
            criterion["priority"] == "must"
            and entry_map.get(criterion["id"], {}).get("status")
            in {"partially-met", "not-met"}
            for criterion in criteria
        )
        blocked = any(
            criterion["priority"] == "must"
            and entry_map.get(criterion["id"], {}).get("status") == "unknown"
            for criterion in criteria
        )
        gate_status = "fail" if failed else "blocked" if blocked else "pass"
        expected_summary = {
            "total_weight": total_weight,
            "assessed_weight": assessed_weight,
            "coverage_percent": coverage,
            "weighted_score": weighted,
            "gate_status": gate_status,
            "must_gaps": must_gaps,
            "unknown_criteria": unknown,
        }
        for field, expected in expected_summary.items():
            actual = summary[field]
            if actual != expected:
                self.error(
                    f"evaluation-scorecard summary {field} is {actual!r}, expected {expected!r}"
                )

        for name, relative in state["artifacts"].items():
            try:
                path = contained_path(self.root, relative)
            except ValueError as error:
                self.error(f"state artifact {name}: {error}")
                continue
            if not path.is_file():
                self.error(f"state artifact {name} does not exist: {relative}")
                continue
            expected = STATE_ARTIFACTS.get(name)
            if expected is not None and path != (self.root / expected).resolve():
                self.error(
                    f"state artifact {name} must be the validated file {expected}, not {relative}"
                )

        if preservation["teardown_id"] != state["teardown_id"]:
            self.error("preservation teardown_id does not match state")
        artifact_ids = [artifact["id"] for artifact in preservation["artifacts"]]
        repeated = duplicates(artifact_ids)
        if repeated:
            self.error(f"duplicate preservation artifact ids: {sorted(repeated)}")
        # Compare preserved files by resolved path, never by spelling:
        # "./pairs.jsonl" and "pairs.jsonl" are the same file.
        pairs_path = (self.root / REQUIRED["pairs"]).resolve()
        spellings_by_file: dict[Path, list[str]] = {}
        for artifact in preservation["artifacts"]:
            preserved: list[Path] = []
            for file_entry in artifact.get("files", []):
                try:
                    path = contained_path(self.root, file_entry["path"])
                except ValueError as error:
                    self.error(f"preservation artifact {artifact['id']}: {error}")
                    continue
                preserved.append(path)
                spellings_by_file.setdefault(path, []).append(file_entry["path"])
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
                and pairs_path in preserved
                and artifact.get("record_count") != len(pairs)
            ):
                self.error(
                    f"replay-corpus record_count does not match pairs.jsonl "
                    f"in preservation artifact {artifact['id']}"
                )
        for path, spellings in spellings_by_file.items():
            if len(spellings) > 1:
                self.error(
                    f"preserved file appears in multiple artifacts: "
                    f"{path.relative_to(self.root).as_posix()} (listed as {spellings})"
                )

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
